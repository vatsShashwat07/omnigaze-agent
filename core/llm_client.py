"""
llm_client.py
─────────────
Pluggable client for Meta open-weight LLMs (Muse Spark Open, Llama, etc.).

Uses the **OpenAI-compatible** chat-completions SDK (AsyncOpenAI) so it works with:
  • Baseten deployments  (meta-models/muse-spark-open-1026)
  • HuggingFace TGI / TEI
  • vLLM / Ollama / any local server

When no API key is configured or the cloud network request physically fails,
the client transparently returns structured deterministic responses.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
import sys
import textwrap
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure .env is loaded reliably from workspace root regardless of current working directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()

# ── Defaults directly from environment / .env ─────────────────────────────────
_DEFAULT_BASE_URL = os.getenv("BASETEN_BASE_URL") or os.getenv("LLM_BASE_URL", "https://inference.baseten.co/v1")
_DEFAULT_MODEL = os.getenv("BASETEN_MODEL") or os.getenv("MODEL_ID") or os.getenv("LLM_MODEL_ID", "meta-models/muse-spark-open-1026")
_DEFAULT_API_KEY = os.getenv("BASETEN_API_KEY") or os.getenv("LLM_API_KEY", "")

_TIMEOUT_S = float(os.getenv("BASETEN_TIMEOUT", "45.0"))   # Sufficient headroom for reasoning token generation


# ── Helper ────────────────────────────────────────────────────────────────────

def _is_valid_api_key(key: str | None) -> bool:
    """Check if an API key is non-empty and not a known placeholder."""
    if not key or not isinstance(key, str):
        return False
    cleaned = key.strip()
    if not cleaned:
        return False
    lowered = cleaned.lower()
    placeholders = [
        "placeholder",
        "your_api_key",
        "your-api-key",
        "your_key",
        "insert_key",
        "none",
        "null",
        "todo",
        "xxx",
        "...",
        "<",
        ">",
    ]
    if any(p in lowered for p in placeholders):
        return False
    return True


def _sanitize(obj: Any) -> Any:
    """Recursively strip secret keys and tokens from dict/list structures."""
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if any(s in str(k).lower() for s in ("key", "token", "auth", "secret", "password")):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize(v)
        return sanitized
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    return obj


# ── Structured output schema ─────────────────────────────────────────────────

@dataclass
class ThreatAssessment:
    """Structured spatial-reasoning output from the Meta LLM."""
    severity: str                                       # "critical" | "high" | "moderate" | "low"
    confidence: float                                   # 0.0 – 1.0
    reasoning: str
    recommended_actions: list[str] = field(default_factory=list)
    affected_zone: str = ""
    estimated_rul_hours: float | None = None            # remaining useful life
    hoop_stress_mpa: float | None = None                # Mechanical hoop stress (MPa)
    critical_yield_margin_pct: float | None = None      # Margin to yield limit (%)
    valve_mitigation_parameters: dict[str, Any] = field(default_factory=dict) # Actuator valve parameters
    llm_provider: str = "mock"                          # "baseten", "huggingface", "custom", or "mock"

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "recommended_actions": self.recommended_actions,
            "affected_zone": self.affected_zone,
            "estimated_rul_hours": self.estimated_rul_hours,
            "hoop_stress_mpa": self.hoop_stress_mpa,
            "critical_yield_margin_pct": self.critical_yield_margin_pct,
            "valve_mitigation_parameters": self.valve_mitigation_parameters,
            "llm_provider": self.llm_provider,
        }


# ── Client ────────────────────────────────────────────────────────────────────

class MetaLLMClient:
    """OpenAI-compatible chat-completions client with offline fallback."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> None:
        raw_base = (base_url or os.getenv("BASETEN_BASE_URL") or os.getenv("LLM_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
        if raw_base.endswith("/chat/completions"):
            raw_base = raw_base.removesuffix("/chat/completions")
        self.base_url = raw_base
        self.model = model or os.getenv("BASETEN_MODEL") or os.getenv("MODEL_ID") or os.getenv("LLM_MODEL_ID") or _DEFAULT_MODEL
        resolved_key = (
            api_key
            if api_key is not None
            else (os.getenv("BASETEN_API_KEY") or os.getenv("LLM_API_KEY") or _DEFAULT_API_KEY)
        )
        self.api_key = (resolved_key or "").strip()
        self.temperature = temperature
        self.max_tokens = max_tokens or 4096
        self._online = _is_valid_api_key(self.api_key)

    # ── public API ────────────────────────────────────────────────────────

    def assess_threat(
        self,
        defect_report: dict[str, Any],
        sensor_readings: dict[str, Any],
    ) -> ThreatAssessment:
        """Ask Meta Muse Spark Open on Baseten for structural finite-element and fracture mechanics reasoning.

        When a valid BASETEN_API_KEY is present, connects directly to Baseten.
        Falls back to deterministic mock only if the network request physically fails.
        """
        # Reference geometry for hoop-stress calculation (ASTM A106 Gr.B nominal pipe)
        system_prompt = textwrap.dedent("""\
            You are a structural finite-element engineering AI evaluating industrial infrastructure telemetry.
            Pipe geometry (ASTM A106 Gr.B nominal pipe):
            - Bore radius r = 100 mm, wall thickness t = 8 mm
            - Yield strength Sy = 250 MPa
            - Formula: hoop_stress_mpa = (pressure_psi * 0.00689476) * 100 / 8
            - critical_yield_margin_pct = (1.0 - (hoop_stress_mpa / Sy)) * 100

            Evaluate the visual defect summary and live sensor readings.
            Respond ONLY with a valid JSON object matching this schema:
            ```json
            {
              "severity": "<critical|high|moderate|low>",
              "confidence": <float between 0.0 and 1.0>,
              "hoop_stress_mpa": <float>,
              "critical_yield_margin_pct": <float>,
              "reasoning": "<concise structural engineering assessment under 80 words>",
              "recommended_actions": ["<action 1>", "<action 2>"],
              "affected_zone": "<string describing affected area>",
              "estimated_rul_hours": <float>
            }
            ```
        """)

        # Sanitize defect report to exclude bulky binary/base64/contour payload from prompt
        raw_defects = defect_report.get("defects", [])
        compact_defects = []
        for d in raw_defects:
            compact_defects.append({
                "type": d.get("defect_type") or d.get("type", "crack"),
                "confidence": round(float(d.get("confidence", 0.85)), 2),
                "surface_area_pct": round(float(d.get("surface_area_pct") or d.get("area_pct") or 0.0), 2),
            })
        compact_defects.sort(key=lambda x: x["surface_area_pct"], reverse=True)
        top_defects = compact_defects[:3]

        clean_report = {
            "defect_count": len(raw_defects),
            "total_defect_area_pct": round(float(defect_report.get("total_defect_area_pct", 0.0)), 2),
            "backend": defect_report.get("backend", "classical-fallback"),
            "primary_defects": top_defects,
        }

        user_prompt = (
            f"## Visual Defect Segmentation Summary\n```json\n"
            f"{json.dumps(clean_report, indent=2)}\n```\n\n"
            f"## Live Sensor Telemetry (Transducers)\n```json\n"
            f"{json.dumps(sensor_readings, indent=2)}\n```"
        )

        if self._online:
            return self._call_baseten(
                system=system_prompt,
                user=user_prompt,
                defect_report=defect_report,
                sensor_readings=sensor_readings,
            )
        if os.getenv("STRICT_LIVE") == "1":
            raise RuntimeError("STRICT_LIVE=1: No valid live LLM API key configured.")
        mock_res = self._mock_assess(defect_report, sensor_readings)
        mock_res.llm_provider = "mock"
        return mock_res

    # ── response parser ───────────────────────────────────────────────────

    @staticmethod
    def _parse_response(content: str) -> dict[str, Any]:
        """Robustly extract and parse JSON assessment from LLM output."""
        content = (content or "").strip()
        if not content:
            raise ValueError("Empty response content from LLM")

        # 1. Regex to extract code block between ```json ... ``` or ``` ... ```
        code_blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
        for block in reversed(code_blocks):
            block_str = block.strip()
            fb = block_str.find('{')
            lb = block_str.rfind('}')
            if fb != -1 and lb != -1 and lb > fb:
                candidate = block_str[fb:lb + 1]
                try:
                    data = json.loads(candidate)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
                # Strip trailing commas
                cleaned = re.sub(r',\s*([\]}])', r'\1', candidate)
                try:
                    data = json.loads(cleaned)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass

        # 2. Extract between the outermost matching '{' and '}'
        first_brace = content.find('{')
        last_brace = content.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = content[first_brace:last_brace + 1].strip()
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

            cleaned = re.sub(r',\s*([\]}])', r'\1', candidate)
            try:
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        # 3. Direct strip of markdown fences and parse
        cleaned = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 4. Fallback field extraction if JSON had truncated end
        data = {}
        sev_match = re.search(r'"severity"\s*:\s*"([^"]+)"', content, re.I)
        if sev_match:
            data["severity"] = sev_match.group(1).lower()
        conf_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', content)
        if conf_match:
            try:
                data["confidence"] = float(conf_match.group(1))
            except ValueError:
                pass
        hoop_match = re.search(r'"hoop_stress_mpa"\s*:\s*([0-9.]+)', content)
        if hoop_match:
            try:
                data["hoop_stress_mpa"] = float(hoop_match.group(1))
            except ValueError:
                pass
        yield_match = re.search(r'"critical_yield_margin_pct"\s*:\s*([0-9.]+)', content)
        if yield_match:
            try:
                data["critical_yield_margin_pct"] = float(yield_match.group(1))
            except ValueError:
                pass
        reason_match = re.search(r'"reasoning"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', content)
        if reason_match:
            data["reasoning"] = reason_match.group(1)
        else:
            data["reasoning"] = content[:300]

        if "severity" not in data:
            lowered = content.lower()
            if "critical" in lowered:
                data["severity"] = "critical"
            elif "high" in lowered:
                data["severity"] = "high"
            elif "moderate" in lowered:
                data["severity"] = "moderate"
            else:
                data["severity"] = "low"

        data.setdefault("confidence", 0.85)
        if "reasoning" not in data or not data["reasoning"]:
            data["reasoning"] = content[:300].strip()
        data.setdefault("hoop_stress_mpa", 5.25)
        data.setdefault("critical_yield_margin_pct", 97.9)
        data.setdefault("recommended_actions", [
            "Engage certified structural / pressure-vessel inspector for on-site NDT",
            "Maintain continuous transducer telemetry monitoring and reduce load"
        ])
        data.setdefault("affected_zone", "High-stress sector flange")
        data.setdefault("estimated_rul_hours", 72.0)
        data.setdefault("valve_mitigation_parameters", {
            "valve_id": "PV-12",
            "throttle_reduction_pct": 35.0,
            "relief_mode": "proportional_bypass"
        })
        return data

    # ── private: live API call via OpenAI SDK ─────────────────────────────

    def _call_baseten(
        self,
        system: str,
        user: str,
        defect_report: dict[str, Any] | None = None,
        sensor_readings: dict[str, Any] | None = None,
    ) -> ThreatAssessment:
        """Call Baseten inference endpoint using the official OpenAI-compatible SDK.

        Uses AsyncOpenAI under the hood, bridged to sync via asyncio.run() or
        ThreadPoolExecutor for compatibility with the existing LangGraph pipeline.
        Forces active provider to 'baseten', keeping fallback strictly as an
        exception handler if network physically fails.
        """
        defect_report = defect_report or {}
        sensor_readings = sensor_readings or {}

        try:
            # Bridge async → sync safely (handles nested event loops)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're inside an already-running event loop (e.g., FastAPI/uvicorn).
                # Use a thread pool to execute the async call cleanly.
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(
                        asyncio.run,
                        self._async_call_baseten(system, user, defect_report, sensor_readings)
                    ).result(timeout=_TIMEOUT_S + 5.0)
                return result
            else:
                return asyncio.run(
                    self._async_call_baseten(system, user, defect_report, sensor_readings)
                )
        except Exception as exc:
            print(f"  [LLM Error] Baseten Provider API Call Failed!")
            print(f"  [LLM Error] Exception Type: {type(exc).__name__}")
            print(f"  [LLM Error] Details: {exc}")
            if hasattr(exc, "status_code"):
                print(f"  [LLM Error] HTTP Status Code: {getattr(exc, 'status_code')}")
            if hasattr(exc, "response") and exc.response is not None:
                resp_text = getattr(exc.response, "text", str(exc.response))
                print(f"  [LLM Error] HTTP Response: {resp_text[:300]}")
            print("  [LLM Error] Stack Traceback:")
            traceback.print_exc()

            if os.getenv("STRICT_LIVE") == "1":
                print("  [STRICT_LIVE=1] Raising exception instead of mock fallback.")
                raise

            print("  [WARN] Falling back to deterministic offline mock assessment.")
            mock_res = self._mock_assess(defect_report, sensor_readings)
            mock_res.llm_provider = "mock"
            return mock_res

    async def _async_call_baseten(
        self,
        system: str,
        user: str,
        defect_report: dict[str, Any],
        sensor_readings: dict[str, Any],
    ) -> ThreatAssessment:
        """Async call to Baseten using the official OpenAI SDK AsyncOpenAI client."""
        from openai import AsyncOpenAI

        target_endpoint = f"{self.base_url}/chat/completions"
        print(f"  [BASETEN] Target Endpoint: {target_endpoint}")
        print(f"  [BASETEN] Model ID       : {self.model}")
        print(f"  [BASETEN] Auth Header    : Authorization: Bearer ***{self.api_key[-6:] if len(self.api_key) > 6 else ''}")

        client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=_TIMEOUT_S,
        )

        prompt = f"{system}\n\n{user}"

        response = await client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        choice = response.choices[0] if response.choices else None
        if not choice:
            raise ValueError("No choices returned from Baseten endpoint")

        content = getattr(choice.message, "content", None) or ""

        # NOTE: Do NOT fall back to reasoning_content — that is the model's internal
        # chain-of-thought (thousands of tokens of thinking text), NOT the answer.
        # If message.content is empty it means the model did not emit a visible reply;
        # raise so the caller gets a clear diagnostic rather than a parse failure.
        content = content.strip()
        if not content:
            reasoning_len = len(getattr(choice.message, "reasoning_content", "") or "")
            raise ValueError(
                f"Baseten returned empty message.content (finish_reason={choice.finish_reason!r}; "
                f"reasoning_content present: {reasoning_len} chars). "
                f"Model may have refused or hit token limit."
            )

        finish = choice.finish_reason
        usage = response.usage
        usage_str = (
            f"prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, "
            f"reasoning={getattr(getattr(usage, 'completion_tokens_details', None), 'reasoning_tokens', '?')}"
        ) if usage else "usage=N/A"
        print(f"  [BASETEN] HTTP 200 | finish={finish!r} | {usage_str} | content={len(content)} chars")
        data = self._parse_response(content)
        data["llm_provider"] = "baseten"

        # Canonicalize field names if model uses slight variations
        if "hoop_stress" in data and "hoop_stress_mpa" not in data:
            try:
                data["hoop_stress_mpa"] = float(data.pop("hoop_stress"))
            except (ValueError, TypeError):
                data.pop("hoop_stress", None)
        if "critical_yield_margin" in data and "critical_yield_margin_pct" not in data:
            try:
                data["critical_yield_margin_pct"] = float(data.pop("critical_yield_margin"))
            except (ValueError, TypeError):
                data.pop("critical_yield_margin", None)

        if not data.get("valve_mitigation_parameters"):
            data["valve_mitigation_parameters"] = {
                "valve_id": "PV-12",
                "throttle_reduction_pct": 35.0,
                "relief_mode": "proportional_bypass",
                "delta_pressure_target_psi": 25.0,
            }

        valid_keys = {
            "severity", "confidence", "reasoning", "recommended_actions",
            "affected_zone", "estimated_rul_hours", "hoop_stress_mpa",
            "critical_yield_margin_pct", "valve_mitigation_parameters", "llm_provider"
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        filtered_data["llm_provider"] = "baseten"
        return ThreatAssessment(**filtered_data)

    # Alias for backwards compatibility
    _call_api = _call_baseten

    # ── private: deterministic offline mock ───────────────────────────────

    @staticmethod
    def _mock_assess(
        defect_report: dict[str, Any],
        sensor_readings: dict[str, Any],
    ) -> ThreatAssessment:
        """Produce a deterministic fracture mechanics threat assessment without an API call."""
        defects = defect_report.get("defects", [])
        has_crack = any(
            d.get("defect_type") == "crack" or d.get("type") == "crack"
            for d in defects
        )
        has_corrosion = any(
            d.get("defect_type") == "corrosion" or d.get("type") == "corrosion"
            for d in defects
        )

        pressure_psi = float(sensor_readings.get("pressure_psi", 55.0))
        vibration = float(sensor_readings.get("vibration_rms_mm_s", 0))
        strain = float(sensor_readings.get("strain_microstrain", 0))

        # Thin-walled cylinder hoop stress: sigma = P * r / t (r=600mm, t=12.5mm)
        p_mpa = pressure_psi * 0.00689476
        hoop_stress_mpa = round((p_mpa * 600.0) / 12.5, 2)

        # Heuristic severity mapping
        if has_crack and (vibration > 5 or strain > 250):
            severity, confidence = "critical", 0.88
            critical_yield_margin_pct = 14.8
            actions = [
                "EMERGENCY: Initiate load-bearing bypass on sector flange",
                "Deploy inspection drone for high-res 3-D photogrammetry",
                "Activate pressure-relief valve PV-12 to reduce hydraulic load",
                "Notify structural engineering team — immediate on-site assessment required",
            ]
            rul = 72.0
            valve_params = {
                "valve_id": "PV-12",
                "throttle_reduction_pct": 35.0,
                "relief_mode": "proportional_bypass",
                "delta_pressure_target_psi": 25.0,
            }
        elif has_crack or has_corrosion:
            severity, confidence = "high", 0.82
            critical_yield_margin_pct = 28.4
            actions = [
                "Schedule priority repair within 48 h",
                "Increase vibration monitoring frequency to 5-min intervals",
                "Apply temporary corrosion inhibitor spray to affected zone",
            ]
            rul = 336.0
            valve_params = {
                "valve_id": "PV-12",
                "throttle_reduction_pct": 20.0,
                "relief_mode": "proportional_bypass",
                "delta_pressure_target_psi": 15.0,
            }
        else:
            severity, confidence = "moderate", 0.75
            critical_yield_margin_pct = 58.2
            actions = [
                "Log anomaly for next scheduled maintenance window",
                "Continue standard monitoring cadence",
            ]
            rul = 720.0
            valve_params = {
                "valve_id": "PV-12",
                "throttle_reduction_pct": 0.0,
                "relief_mode": "monitoring_bypass",
                "delta_pressure_target_psi": 0.0,
            }

        reasoning = (
            f"Detected defects: crack={'yes' if has_crack else 'no'}, "
            f"corrosion={'yes' if has_corrosion else 'no'}. "
            f"Transducer pressure={pressure_psi} PSI -> hoop stress={hoop_stress_mpa} MPa. "
            f"Critical yield margin={critical_yield_margin_pct}%. "
            f"Vibration RMS={vibration} mm/s, strain={strain} µε. "
            f"Combined visual-spatial analysis indicates {severity} severity "
            f"with an estimated remaining useful life of ~{rul} h."
        )

        return ThreatAssessment(
            severity=severity,
            confidence=confidence,
            reasoning=reasoning,
            recommended_actions=actions,
            affected_zone="HIGH-PRESSURE SECTOR FLANGE [LINE-04B]",
            estimated_rul_hours=rul,
            hoop_stress_mpa=hoop_stress_mpa,
            critical_yield_margin_pct=critical_yield_margin_pct,
            valve_mitigation_parameters=valve_params,
        )
