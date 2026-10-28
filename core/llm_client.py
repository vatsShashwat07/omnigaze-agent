"""
llm_client.py
─────────────
Pluggable client for Meta open-weight LLMs (Muse Spark Open, Llama, etc.).

Speaks the **OpenAI-compatible** chat-completions protocol so it works with:
  • Baseten deployments  (meta-models/muse-spark-open-1026)
  • HuggingFace TGI / TEI
  • vLLM / Ollama / any local server

When no API key is configured the client transparently returns structured
mock responses so the full pipeline can be demonstrated offline.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Defaults ──────────────────────────────────────────────────────────────────
_DEFAULT_BASE_URL = os.getenv("BASETEN_BASE_URL") or os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
_DEFAULT_MODEL = os.getenv("MODEL_ID") or os.getenv("LLM_MODEL_ID", "meta-models/muse-spark-open")
_DEFAULT_API_KEY = os.getenv("BASETEN_API_KEY") or os.getenv("LLM_API_KEY", "")

_TIMEOUT_S = 60


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

        Falls back to a deterministic mock when no API key is set or when calls fail.
        """
        system_prompt = textwrap.dedent("""\
            You are OmniGaze-Agent's spatial reasoning engine. Given a visual
            defect segmentation report and live sensor telemetry for a piece of
            physical infrastructure, you must:

            1. Assess the structural threat severity (critical / high / moderate / low).
            2. Explain the spatial reasoning behind your assessment.
            3. Recommend concrete mitigation actions.
            4. Estimate remaining useful life in hours if possible.

            Keep internal reasoning concise. You must strictly output the final assessment as a valid, closed JSON object enclosed in ```json ... ```.

            Respond ONLY with valid JSON matching this schema:
            {
              "severity": "<critical|high|moderate|low>",
              "confidence": <float 0-1>,
              "reasoning": "<string>",
              "recommended_actions": ["<action1>", ...],
              "affected_zone": "<string>",
              "estimated_rul_hours": <float|null>
            }
        """)

        user_prompt = (
            f"## Visual Defect Report\n```json\n"
            f"{json.dumps(defect_report, indent=2)}\n```\n\n"
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

    # ── private: live API call ────────────────────────────────────────────

    def _call_baseten(
        self,
        system: str,
        user: str,
        defect_report: dict[str, Any] | None = None,
        sensor_readings: dict[str, Any] | None = None,
    ) -> ThreatAssessment:
        defect_report = defect_report or {}
        sensor_readings = sensor_readings or {}

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        resp = None
        for attempt in range(2):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT_S)
                resp.raise_for_status()

                if hasattr(resp, "model_dump"):
                    raw_dict = resp.model_dump()
                else:
                    try:
                        raw_dict = resp.json()
                    except Exception:
                        raw_dict = {"text": resp.text}

                choices = raw_dict.get("choices", []) if isinstance(raw_dict, dict) else []
                if not choices:
                    raise ValueError(f"No choices returned from LLM endpoint (attempt {attempt + 1})")

                message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                content = message.get("content")

                # If message.content is None/empty, also check reasoning_content or other candidate fields
                if not content:
                    for field_name in ("reasoning_content", "reasoning", "thought", "text"):
                        candidate = message.get(field_name) or (choices[0].get(field_name) if isinstance(choices[0], dict) else None)
                        if candidate:
                            content = candidate
                            break

                content = (content or "").strip()
                if not content:
                    if attempt == 0:
                        print(f"  [LLM Warning] Empty content on attempt 1. Candidate keys in message: {list(message.keys())}. Retrying once with max_tokens={self.max_tokens}...")
                        time.sleep(0.5)
                        continue
                    raise ValueError("Empty or None content returned from LLM endpoint after retry")

                data = self._parse_response(content)
                data["llm_provider"] = "baseten"
                return ThreatAssessment(**data)

            except Exception as exc:
                print(f"  [LLM Error] Provider failed! type(exc): {type(exc).__name__} | Details: {exc}")
                if resp is not None:
                    if hasattr(resp, "model_dump"):
                        print(f"  [LLM Response model_dump]: {json.dumps(_sanitize(resp.model_dump()), indent=2, default=str)}")
                    else:
                        try:
                            print(f"  [LLM Response Payload]: {json.dumps(_sanitize(resp.json()), indent=2, default=str)}")
                        except Exception:
                            print(f"  [LLM Raw Response]: status={resp.status_code}, text={resp.text[:500]}")

                if attempt == 0:
                    time.sleep(0.5)
                    continue

                if os.getenv("STRICT_LIVE") == "1":
                    print("  [STRICT_LIVE=1] Raising exception instead of mock fallback.")
                    raise

                print("  ⚠  Falling back to deterministic offline mock assessment.")
                mock_res = self._mock_assess(defect_report, sensor_readings)
                mock_res.llm_provider = "mock"
                return mock_res

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
                "EMERGENCY: Initiate load-bearing bypass on sector (simulated)",
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
            affected_zone="sector-flange (simulated)",
            estimated_rul_hours=rul,
        )
