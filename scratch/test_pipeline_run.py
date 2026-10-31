import asyncio
import json
import os
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import app, HITL_APPROVALS
import httpx

async def main():
    print("[TEST] Running real server stream for SC-004 with provider=baseten...", flush=True)
    # Pre-authorize SC-004 so automated tests do not block on the 30s human-in-the-loop interlock
    HITL_APPROVALS["SC-004"] = {"approved": True, "authorized_by": "Test Suite Automated Verification"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        async with client.stream("GET", "/api/stream/SC-004?provider=baseten") as response:
            print(f"[TEST] Response status: {response.status_code}", flush=True)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            current_event = None
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                    print(f"\n[EVENT] {current_event}", flush=True)
                elif line.startswith("data:"):
                    data_str = line.replace("data:", "", 1).strip()
                    try:
                        parsed = json.loads(data_str)
                        if current_event == "reasoning":
                            print(f"[REASONING DATA] Provider: {parsed.get('llm_provider')} | Model: {parsed.get('model')} | Severity: {parsed.get('severity')}", flush=True)
                            print(f"[REASONING OUTPUT] {parsed.get('reasoning')[:180]}...", flush=True)
                            assert parsed.get("llm_provider") == "baseten", f"Expected provider 'baseten', got '{parsed.get('llm_provider')}'"
                        elif current_event == "complete":
                            print(f"[COMPLETE DATA] {parsed}", flush=True)
                            break
                        else:
                            node = parsed.get("node") or current_event
                            print(f"  [DATA] node={node}", flush=True)
                    except json.JSONDecodeError:
                        print(f"  [RAW DATA] {data_str[:120]}...", flush=True)

    print("\n[TEST] ✅ Live Baseten Meta Muse Spark Open pipeline run verified successfully!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
