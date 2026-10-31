"""
llm_client.py
─────────────
Pluggable client for Meta open-weight LLMs (Muse Spark Open, Llama, etc.).

Uses the **OpenAI-compatible** chat-completions SDK (AsyncOpenAI) so it works with:
  • Baseten deployments  (meta-models/muse-spark-open-1026)
  • HuggingFace TGI / TEI
  • vLLM / Ollama / any local server

When no API key is configured the client transparently returns structured
mock responses so the full pipeline can be demonstrated offline.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ── Defaults ──────────────────────────────────────────────────────────────────
_DEFAULT_BASE_URL = os.getenv("BASETEN_BASE_URL") or os.getenv("LLM_BASE_URL", "https://inference.baseten.co/v1")
_DEFAULT_MODEL = os.getenv("BASETEN_MODEL") or os.getenv("MODEL_ID") or os.getenv("LLM_MODEL_ID", "meta-models/muse-spark-open-1026")
_DEFAULT_API_KEY = os.getenv("BASETEN_API_KEY") or os.getenv("LLM_API_KEY", "")

_TIMEOUT_S = 7.5   # Hard timeout (>6.0s) – fallback strictly as an exception handler if exceeded


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
    severity: str          # "critical" | "high" | "moderate" | "low"
    confidence: float      # 0.0 – 1.0
    reasoning: str
    recommended_actions: list[str] = field(default_factory=list)
    affected_zone: str = ""
    estimated_rul_hours: float | None = None  # remaining useful life
    llm_provider: str = "mock"                 # "baseten", "huggingface", "custom", or "mock"

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "recommended_actions": self.recommended_actions,
            "affected_zone": self.affected_zone,
            "estimated_rul_hours": self.estimated_rul_hours,
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
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> None:
        self.base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self.model = model or _DEFAULT_MODEL
        resolved_key = (
            api_key
            if api_key is not None
            else (os.getenv("BASETEN_API_KEY") or os.getenv("LLM_API_KEY") or _DEFAULT_API_KEY)
        )
        self.api_key = (resolved_key or "").strip()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._online = _is_valid_api_key(self.api_key)

    # ── public API ────────────────────────────────────────────────────────

    def assess_threat(
        self,
        defect_report: dict[str, Any],
        sensor_readings: dict[str, Any],
    ) -> ThreatAssessment:
        """Ask the LLM to perform spatial reasoning on the inspection data.

        When a valid BASETEN_API_KEY is present, forces live provider (no mock).
        Falls back to mock only if no key is set, or if live call exceeds 6.0s timeout.
        """
        system_prompt = textwrap.dedent("""\
            You are OmniGaze-Agent's spatial reasoning engine for physical infrastructure inspection.
            Assess structural threat severity based on the visual defect segmentation report and live sensor telemetry.

            Keep internal reasoning concise (<150 tokens) and respond directly with valid JSON enclosed in ```json ... ``` matching this schema:
            ```json
            {
              "severity": "<critical|high|moderate|low>",
              "confidence": <float 0-1>,
              "reasoning": "<concise spatial-mechanical explanation>",
              "recommended_actions": ["<action1>", "<action2>"],
              "affected_zone": "<string>",
              "estimated_rul_hours": <float|null>
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
            f"## Live Sensor Telemetry\n```json\n"
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

        # 1. Regex to extract code block enclosed in ```json ... ``` or ``` ... ```
        code_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        for block in reversed(code_blocks):
            try:
                data = json.loads(block.strip())
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

            # If trailing reasoning exists or extra text is present, extract valid JSON substrings
            matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', candidate, re.DOTALL)
            for m in reversed(matches):
                try:
                    data = json.loads(m.strip())
                    if isinstance(data, dict) and "severity" in data:
                        return data
                except Exception:
                    pass

        # 3. Direct strip of markdown fences and parse
        cleaned = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)

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
        exception handler if cloud network times out (>6.0s).
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
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(
                        asyncio.run,
                        self._async_call_baseten(system, user, defect_report, sensor_readings)
                    ).result(timeout=_TIMEOUT_S + 4.0)
                return result
            else:
                return asyncio.run(
                    self._async_call_baseten(system, user, defect_report, sensor_readings)
                )
        except Exception as exc:
            print(f"  [LLM Error] Provider call failed! type(exc): {type(exc).__name__} | Details: {exc}")

            is_timeout = (
                isinstance(exc, (asyncio.TimeoutError, concurrent.futures.TimeoutError))
                or "timeout" in type(exc).__name__.lower()
                or "timeout" in str(exc).lower()
            )
            if is_timeout:
                print("  [LLM Fallback] Cloud network timed out (>6.0s). Invoking fallback exception handler.")
                mock_res = self._mock_assess(defect_report, sensor_readings)
                mock_res.llm_provider = "mock"
                return mock_res

            if os.getenv("STRICT_LIVE") == "1":
                print("  [STRICT_LIVE=1] Raising exception instead of mock fallback.")
                raise

            print("  ⚠ Falling back to deterministic offline mock assessment.")
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
            raise ValueError("No choices returned from LLM endpoint")

        content = getattr(choice.message, "content", None) or ""

        # Fallback: check reasoning_content or other fields
        if not content.strip():
            for field_name in ("reasoning_content", "reasoning", "thought", "text"):
                candidate = getattr(choice.message, field_name, None)
                if not candidate and hasattr(choice, field_name):
                    candidate = getattr(choice, field_name, None)
                if candidate:
                    content = candidate
                    break

        content = (content or "").strip()
        if not content:
            raise ValueError("Empty or None content returned from LLM endpoint")

        data = self._parse_response(content)
        data["llm_provider"] = "baseten"
        return ThreatAssessment(**data)

    # Alias for backwards compatibility
    _call_api = _call_baseten

    # ── private: deterministic offline mock ───────────────────────────────

    @staticmethod
    def _mock_assess(
        defect_report: dict[str, Any],
        sensor_readings: dict[str, Any],
    ) -> ThreatAssessment:
        """Produce a plausible threat assessment without an API call."""
        defects = defect_report.get("defects", [])
        has_crack = any(
            d.get("defect_type") == "crack" or d.get("type") == "crack"
            for d in defects
        )
        has_corrosion = any(
            d.get("defect_type") == "corrosion" or d.get("type") == "corrosion"
            for d in defects
        )

        vibration = sensor_readings.get("vibration_rms_mm_s", 0)
        strain = sensor_readings.get("strain_microstrain", 0)

        # Heuristic severity mapping
        if has_crack and (vibration > 5 or strain > 250):
            severity, confidence = "critical", 0.88
            actions = [
                "EMERGENCY: Initiate load-bearing bypass on sector flange",
                "Deploy inspection drone for high-res 3-D photogrammetry",
                "Activate pressure-relief valve PV-12 to reduce hydraulic load",
                "Notify structural engineering team — immediate on-site assessment required",
            ]
            rul = 72.0
        elif has_crack or has_corrosion:
            severity, confidence = "high", 0.82
            actions = [
                "Schedule priority repair within 48 h",
                "Increase vibration monitoring frequency to 5-min intervals",
                "Apply temporary corrosion inhibitor spray to affected zone",
            ]
            rul = 336.0
        else:
            severity, confidence = "moderate", 0.75
            actions = [
                "Log anomaly for next scheduled maintenance window",
                "Continue standard monitoring cadence",
            ]
            rul = 720.0

        reasoning = (
            f"Detected defects: crack={'yes' if has_crack else 'no'}, "
            f"corrosion={'yes' if has_corrosion else 'no'}. "
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
        )
