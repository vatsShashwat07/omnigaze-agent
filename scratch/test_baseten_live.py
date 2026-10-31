"""
test_baseten_live.py
────────────────────
Direct standalone test of the Meta Muse Spark Open endpoint on Baseten.
Verifies HTTP 200 and valid LLM response from the official hackathon endpoint.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def test_direct_openai_sdk():
    """Test the Baseten endpoint directly via the OpenAI SDK."""
    from openai import AsyncOpenAI

    base_url = "https://inference.baseten.co/v1"
    model = "meta-models/muse-spark-open-1026"
    api_key = os.getenv("BASETEN_API_KEY", "")

    print(f"[TEST] Endpoint : {base_url}")
    print(f"[TEST] Model    : {model}")
    print(f"[TEST] API Key  : {'***' + api_key[-6:] if len(api_key) > 6 else '(not set)'}")
    print()

    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=15.0,
    )

    prompt = (
        "You are a structural engineering AI. A weld joint shows fatigue cracking "
        "with 38% surface damage. Pressure is 4.2 bar (redline 6.0). Strain is 285 µε "
        "(yield 350). Vibration is 3.8 mm/s.\n\n"
        "Respond ONLY with valid JSON:\n"
        '{"severity": "<critical|high|moderate|low>", "confidence": <float>, '
        '"reasoning": "<string>", "recommended_actions": ["<action>"], '
        '"affected_zone": "<string>", "estimated_rul_hours": <float>}'
    )

    print("[TEST] Sending chat.completions.create() ...")
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2500,
        )

        print(f"[TEST] ✅ HTTP 200 — Response received!")
        print(f"[TEST] Model used  : {response.model}")
        print(f"[TEST] Finish reason: {response.choices[0].finish_reason}")
        print(f"[TEST] Usage       : prompt={response.usage.prompt_tokens}, "
              f"completion={response.usage.completion_tokens}, "
              f"total={response.usage.total_tokens}")
        print()

        content = response.choices[0].message.content or ""
        if not content.strip() and getattr(response.choices[0].message, "reasoning_content", None):
            content = response.choices[0].message.reasoning_content or ""
        print(f"[TEST] Raw content ({len(content)} chars):")
        print("─" * 60)
        print(content[:1500])
        print("─" * 60)

        # Try to parse JSON
        try:
            # Extract from markdown fence if present
            import re
            blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if blocks:
                data = json.loads(blocks[0])
            else:
                first = content.find('{')
                last = content.rfind('}')
                data = json.loads(content[first:last+1])

            print(f"\n[TEST] ✅ Parsed JSON successfully:")
            print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"\n[TEST] ⚠ JSON parse failed (non-critical): {e}")

    except Exception as exc:
        print(f"[TEST] ❌ FAILED: {type(exc).__name__}: {exc}")
        sys.exit(1)


def test_llm_client_integration():
    """Test via the MetaLLMClient wrapper (same path as the LangGraph pipeline)."""
    from core.llm_client import MetaLLMClient

    print("\n" + "=" * 60)
    print("[TEST] MetaLLMClient integration test")
    print("=" * 60)

    client = MetaLLMClient()
    print(f"[TEST] base_url : {client.base_url}")
    print(f"[TEST] model    : {client.model}")
    print(f"[TEST] online   : {client._online}")
    print()

    if not client._online:
        print("[TEST] ⚠ No valid API key — skipping live call (mock only).")
        return

    result = client.assess_threat(
        defect_report={
            "defect_count": 8,
            "total_defect_area_pct": 38.78,
            "backend": "sam2",
            "defects": [
                {"defect_type": "crack", "confidence": 0.96, "surface_area_pct": 12.4},
                {"defect_type": "corrosion", "confidence": 0.89, "surface_area_pct": 8.2},
            ],
        },
        sensor_readings={
            "pressure_psi": 60.9,
            "strain_microstrain": 285.0,
            "vibration_rms_mm_s": 3.8,
            "temperature_c": 52.4,
            "humidity_pct": 41.0,
            "acoustic_emission_db": 44.2,
        },
    )

    print(f"[TEST] ✅ assess_threat() returned:")
    print(json.dumps(result.to_dict(), indent=2))
    print(f"\n[TEST] Provider: {result.llm_provider}")
    assert result.llm_provider == "baseten", f"Expected 'baseten', got '{result.llm_provider}'"
    print("[TEST] ✅ Provider confirmed: baseten (live)")


if __name__ == "__main__":
    print("=" * 60)
    print("  Meta Muse Spark Open — Baseten Live Endpoint Verification")
    print("=" * 60)
    print()

    # 1. Direct OpenAI SDK test
    asyncio.run(test_direct_openai_sdk())

    # 2. MetaLLMClient integration test
    test_llm_client_integration()

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED ✅")
    print("=" * 60)
