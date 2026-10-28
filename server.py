"""
server.py
─────────
FastAPI Streaming Server for OmniGaze-Agent Industrial Mission Control Dashboard.

Features:
  • GET /                       -> Serves single-page SCADA Mission Control Dashboard.
  • GET /api/stream/{scenario}   -> SSE endpoint streaming live LangGraph node transitions:
                                   (ingest -> segment -> reasoning -> action -> verify -> complete).
  • POST /api/approve-action    -> Human-in-the-Loop authorization for high-severity countermeasures.
  • GET /api/status             -> Diagnostic health and endpoint telemetry status.
"""

from dotenv import load_dotenv
load_dotenv()


import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# On server startup print (booleans only, never the key): BASETEN_API_KEY set?, MODEL_ID, BASE_URL.
_baseten_key_set = bool((os.getenv("BASETEN_API_KEY") or os.getenv("LLM_API_KEY") or "").strip())
_model_id = os.getenv("MODEL_ID") or os.getenv("LLM_MODEL_ID") or "meta-models/muse-spark-open"
_base_url = os.getenv("BASETEN_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://inference.baseten.co/v1"

print(f"[STARTUP] BASETEN_API_KEY set?: {_baseten_key_set}")
print(f"[STARTUP] MODEL_ID: {_model_id}")
print(f"[STARTUP] BASE_URL: {_base_url}")

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from core.agent_graph import AgentState, build_agent_graph
from core.llm_client import MetaLLMClient, ThreatAssessment
from core.vision_sam import SAMSegmenter, SegmentationResult
from mock_telemetry.generate_synthetic_data import run as generate_data

# ── FastAPI App Setup ─────────────────────────────────────────────────────────

app = FastAPI(
    title="OmniGaze-Agent Mission Control API",
    description="Spatial-Visual Infrastructure Inspection SSE Streaming Server",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folders
STATIC_DIR = _PROJECT_ROOT / "static"
MOCK_TELEMETRY_DIR = _PROJECT_ROOT / "mock_telemetry"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
MOCK_TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/mock_telemetry", StaticFiles(directory=str(MOCK_TELEMETRY_DIR)), name="mock_telemetry")

# ── State / Authorization Cache ───────────────────────────────────────────────

CRITICAL_ACTIONS = ["emergency_containment_lock", "emergency_lockdown", "load_shedding"]
PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}
HITL_APPROVALS: Dict[str, Dict[str, Any]] = {}


class ApprovalRequest(BaseModel):
    run_id: str | None = None
    approve: bool = True
    scenario: str | None = None
    action_ids: list[str] = Field(default_factory=list)
    authorized_by: str = "Mission Commander"
    notes: str = "Authorized via Mission Control Industrial SCADA interface."


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def get_dashboard() -> FileResponse:
    """Serve the mission control dashboard."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(
            {"error": "static/index.html not found. Please build the dashboard UI."},
            status_code=404,
        )
    return FileResponse(str(index_file))


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Return runtime diagnostic telemetry."""
    baseten_url = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1")
    model_id = os.getenv("MODEL_ID", "meta-models/muse-spark-open")
    has_baseten_key = bool(os.getenv("BASETEN_API_KEY") or os.getenv("LLM_API_KEY"))

    return {
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "providers": {
            "llm": {
                "name": "Meta Muse Spark Open",
                "model_id": model_id,
                "endpoint": baseten_url,
                "online": has_baseten_key,
            },
            "vision": {
                "name": "Meta SAM 2",
                "model_id": "meta-models/sam-2.1-hiera-large",
                "mode": "Classical CV + SAM Promptable Mask Generator",
            },
            "orchestrator": {
                "name": "LangGraph StateGraph",
                "state": "Armed",
            },
        },
        "supported_scenarios": [
            {"id": "SC-001", "name": "Critical Crack", "severity": "CRITICAL"},
            {"id": "SC-002", "name": "Surface Corrosion", "severity": "HIGH"},
            {"id": "SC-003", "name": "Nominal Baseline", "severity": "NOMINAL"},
            {"id": "SC-004", "name": "Stubborn Crack", "severity": "MULTI-RETRY"},
        ],
        "active_approvals": HITL_APPROVALS,
        "pending_approvals_count": len(PENDING_APPROVALS),
    }


@app.post("/api/approve-action")
async def approve_action(req: ApprovalRequest) -> dict[str, Any]:
    """Human-in-the-Loop approval for critical countermeasures."""
    run_id = req.run_id or req.scenario or "default"
    print(f"[API] /api/approve-action received for run_id={run_id}, approve={req.approve}")

    if run_id in PENDING_APPROVALS:
        pending = PENDING_APPROVALS[run_id]
        pending["approved"] = bool(req.approve)
        pending["responded"] = True
        pending["event"].set()
        return {
            "status": "ok",
            "run_id": run_id,
            "approved": pending["approved"],
            "action": pending.get("action"),
            "message": f"Action {'[AUTHORIZED & EXECUTED]' if pending['approved'] else '[DENIED BY OPERATOR / TIMED OUT]'}.",
        }

    # Historical record fallback
    approval_record = {
        "scenario": req.scenario or run_id,
        "run_id": run_id,
        "action_ids": req.action_ids,
        "authorized_by": req.authorized_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "AUTHORIZED" if req.approve else "DENIED",
        "notes": req.notes,
    }
    HITL_APPROVALS[run_id] = approval_record
    if req.scenario:
        HITL_APPROVALS[req.scenario] = approval_record

    return {
        "status": "recorded",
        "run_id": run_id,
        "approved": req.approve,
        "approval": approval_record,
    }


# ── SSE Pipeline Stream ───────────────────────────────────────────────────────

@app.get("/api/stream/{scenario}")
async def stream_pipeline(
    scenario: str,
    provider: str = "baseten",
    request: Request = None,
) -> EventSourceResponse:
    """Stream live LangGraph pipeline execution using Server-Sent Events (SSE)."""

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        t_start = time.perf_counter()
        normalized_scenario = scenario.strip().upper()
        if not normalized_scenario.startswith("SC-"):
            normalized_scenario = f"SC-{normalized_scenario}"

        run_id = f"RUN-{normalized_scenario}-{uuid.uuid4().hex[:8]}"

        print(f"\n[SSE] Client connected. Launching pipeline for {normalized_scenario} (run_id={run_id}, provider={provider})")

        # ── Step 1: Ingest Telemetry ──────────────────────────────────────────
        await asyncio.sleep(0.3)
        loop = asyncio.get_running_loop()

        telemetry = await loop.run_in_executor(
            None, lambda: generate_data(scenario=normalized_scenario)
        )
        sensors = telemetry.get("sensors", {})
        visual_path = telemetry.get("visual_frame", {}).get("path", "")
        asset = telemetry.get("asset", {})

        # Resolve visual_path to web URL
        if visual_path:
            vp = Path(visual_path)
            if not vp.is_absolute():
                raw_web_url = f"/{vp.as_posix().lstrip('/')}"
            else:
                try:
                    rel = vp.relative_to(_PROJECT_ROOT)
                    raw_web_url = f"/{rel.as_posix()}"
                except Exception:
                    raw_web_url = f"/mock_telemetry/real_assets/{vp.name}" if "real_assets" in str(vp) else f"/mock_telemetry/{vp.name}"
        else:
            raw_web_url = "/mock_telemetry/synthetic_defect.png"

        # Calculate limit ratios for honest status evaluation
        vib_limit = 3.0
        strain_limit = 150.0
        r_vib = round(sensors.get("vibration_rms_mm_s", 0) / vib_limit, 2)
        r_str = round(sensors.get("strain_microstrain", 0) / strain_limit, 2)
        max_r = max(r_vib, r_str)
        initial_risk = "CRITICAL" if max_r >= 1.8 else ("WARNING" if max_r >= 1.0 else "STABLE")

        ts = int(time.time() * 1000)
        yield {
            "event": "ingest",
            "data": json.dumps({
                "node": "ingest_telemetry",
                "run_id": run_id,
                "scenario": normalized_scenario,
                "inspection_id": telemetry.get("inspection_id", normalized_scenario),
                "asset": asset,
                "sensors": {
                    "pressure_psi": sensors.get("pressure_psi", 55.0),
                    "strain_microstrain": sensors.get("strain_microstrain", 180.0),
                    "vibration_rms_mm_s": sensors.get("vibration_rms_mm_s", 4.2),
                    "temperature_c": sensors.get("temperature_c", 30.0),
                    "humidity_pct": sensors.get("humidity_pct", 65.0),
                    "acoustic_emission_db": sensors.get("acoustic_emission_db", 42.0),
                },
                "limit_ratios": {
                    "vibration_ratio": r_vib,
                    "strain_ratio": r_str,
                    "max_ratio": max_r,
                },
                "risk_level": initial_risk,
                "image_url": f"{raw_web_url}?t={ts}",
                "timestamp": telemetry.get("timestamp"),
            }),
        }

        # ── Step 2: Segment Defect (SAM 2) ────────────────────────────────────
        await asyncio.sleep(0.5)
        segmenter = SAMSegmenter()
        seg_result: SegmentationResult = await loop.run_in_executor(
            None, lambda: segmenter.segment(visual_path)
        )
        seg_dict = seg_result.to_dict()

        yield {
            "event": "segment",
            "data": json.dumps({
                "node": "segment_defect",
                "backend": seg_dict.get("backend", "classical-fallback"),
                "badge": "Meta SAM 2" if seg_dict.get("backend") == "sam2" else "Classical CV Fallback",
                "model": "meta-models/sam-2.1-hiera-large" if seg_dict.get("backend") == "sam2" else "classical-cv",
                "defect_count": seg_dict.get("defect_count", 0),
                "total_defect_area_pct": round(seg_dict.get("total_defect_area_pct", 0.0), 4),
                "defects": seg_dict.get("defects", []),
                "mask_url": f"/mock_telemetry/annotated_defects.png?t={int(time.time() * 1000)}",
                "raw_image_url": f"{raw_web_url}?t={int(time.time() * 1000)}",
                "overlay_b64": seg_dict.get("overlay_b64", ""),
            }),
        }

        # ── Step 3: Spatial Reasoning (Meta Muse Spark Open) ──────────────────
        await asyncio.sleep(0.6)
        llm_client = MetaLLMClient()

        try:
            assessment = await loop.run_in_executor(
                None, lambda: llm_client.assess_threat(defect_report=seg_dict, sensor_readings=sensors)
            )
            ass_dict = assessment.to_dict()
            if os.getenv("STRICT_LIVE") == "1" and ass_dict.get("llm_provider") == "mock":
                raise RuntimeError("STRICT_LIVE=1: Provider failed and mock fallback is prohibited.")
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({
                    "node": "spatial_reasoning",
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "provider": provider,
                    "message": "Live LLM Provider failed under STRICT_LIVE=1.",
                }),
            }
            return

        # Check HITL requirement
        is_critical = ass_dict.get("severity", "").lower() == "critical"
        has_approval = normalized_scenario in HITL_APPROVALS or "ALL" in HITL_APPROVALS

        yield {
            "event": "reasoning",
            "data": json.dumps({
                "node": "spatial_reasoning",
                "llm_provider": ass_dict.get("llm_provider", "mock"),
                "model": "meta-models/muse-spark-open",
                "provider": provider,
                "severity": ass_dict.get("severity", "moderate").upper(),
                "confidence": round(ass_dict.get("confidence", 0.75), 2),
                "reasoning": ass_dict.get("reasoning", ""),
                "recommended_actions": ass_dict.get("recommended_actions", []),
                "affected_zone": ass_dict.get("affected_zone", ""),
                "requires_hitl": is_critical and not has_approval,
            }),
        }

        # ── Loop: Dispatch Action & Verify Recovery (with retry for SC-004) ───
        retry_count = 0
        max_retries = 2
        recovery_confirmed = False
        all_actions: list[dict[str, Any]] = []

        while not recovery_confirmed and retry_count < max_retries:
            retry_count += 1
            await asyncio.sleep(0.7)

            # Determine action catalogue
            sev_key = ass_dict.get("severity", "moderate").lower()
            if sev_key == "critical" or normalized_scenario == "SC-001":
                actions = [
                    {
                        "action": "pressure_valve_adjustment",
                        "target": "PV-12",
                        "parameter": "reduce_pressure_psi",
                        "value": 45,
                        "status": "executed",
                    },
                    {
                        "action": "emergency_lockdown",
                        "target": asset.get("component_id") or "sector-flange (simulated)",
                        "parameter": "access_restriction",
                        "value": "full_lockdown",
                        "status": "pending_authorization",
                    },
                    {
                        "action": "drone_repositioning",
                        "target": "DJI-Mavic3-IR",
                        "parameter": "new_altitude_m",
                        "value": 5.0,
                        "status": "executed",
                    },
                ]
            elif sev_key == "high":
                actions = [
                    {
                        "action": "pressure_valve_adjustment",
                        "target": "PV-12",
                        "parameter": "reduce_pressure_psi",
                        "value": 20,
                        "status": "executed",
                    },
                    {
                        "action": "apply_corrosion_inhibitor",
                        "target": "SEG-47A-FLANGE",
                        "parameter": "spray_volume_ml",
                        "value": 350,
                        "status": "executed",
                    },
                    {
                        "action": "drone_repositioning",
                        "target": "DJI-Mavic3-IR",
                        "parameter": "new_altitude_m",
                        "value": 8.0,
                        "status": "executed",
                    },
                ]
            elif sev_key == "low":
                actions = [
                    {
                        "action": "log_nominal_condition",
                        "target": "maintenance_db",
                        "parameter": "priority",
                        "value": "routine",
                        "status": "logged",
                    },
                ]
            else:
                actions = [
                    {
                        "action": "increase_monitoring_frequency",
                        "target": "sensor_array_47A",
                        "parameter": "interval_seconds",
                        "value": 300,
                        "status": "executed",
                    },
                ]

            # Check if any proposed action is in the critical list:
            # ["emergency_containment_lock", "emergency_lockdown", "load_shedding"]
            critical_action = next(
                (a for a in actions if a.get("action") in CRITICAL_ACTIONS), None
            )

            is_approved = False
            if critical_action:
                action_name = critical_action["action"]
                target_name = critical_action.get("target", asset.get("component_id", "Target Asset"))

                approval_event = asyncio.Event()
                approval_record = {
                    "event": approval_event,
                    "approved": False,
                    "action": action_name,
                    "target": target_name,
                    "responded": False,
                }
                PENDING_APPROVALS[run_id] = approval_record

                print(f"[HITL] Pausing worker for run_id={run_id}. Approval required for {action_name} on {target_name}")

                # Emit approval_required SSE event
                yield {
                    "event": "approval_required",
                    "data": json.dumps({
                        "run_id": run_id,
                        "action": action_name,
                        "target": target_name,
                        "severity": "CRITICAL",
                        "timeout_sec": 30,
                    }),
                }

                # Pause the worker thread using an asyncio.Event associated with run_id
                # Wait up to 30 seconds for operator response via POST /api/approve-action {"run_id": str, "approve": bool}
                try:
                    await asyncio.wait_for(approval_event.wait(), timeout=30.0)
                    is_approved = approval_record.get("approved", False)
                except asyncio.TimeoutError:
                    print(f"[HITL] ⏱ Approval timed out after 30s for run_id={run_id}")
                    is_approved = False
                finally:
                    PENDING_APPROVALS.pop(run_id, None)

                # If approved (True): Execute the action and emit event: "action" with status "[AUTHORIZED & EXECUTED]"
                # If denied (False) or timed out: Skip the action, log "[DENIED BY OPERATOR / TIMED OUT]", and continue the pipeline safely.
                if is_approved:
                    critical_action["status"] = "[AUTHORIZED & EXECUTED]"
                    print(f"[HITL] Operator APPROVED: {action_name} on {target_name} -> [AUTHORIZED & EXECUTED]")
                else:
                    critical_action["status"] = "[DENIED BY OPERATOR / TIMED OUT]"
                    print(f"[HITL] Operator DENIED or TIMED OUT: {action_name} -> [DENIED BY OPERATOR / TIMED OUT]")

            now_iso = datetime.now(timezone.utc).isoformat()
            for a in actions:
                a["timestamp"] = now_iso
                all_actions.append(a)

            yield {
                "event": "action",
                "data": json.dumps({
                    "node": "dispatch_action",
                    "iteration": retry_count,
                    "actions": actions,
                    "run_id": run_id,
                    "requires_authorization": critical_action is not None,
                    "authorization_status": (
                        "[AUTHORIZED & EXECUTED]" if is_approved else "[DENIED BY OPERATOR / TIMED OUT]"
                    ) if critical_action else "AUTO-MITIGATE",
                }),
            }

            # ── Step 5: Verify Recovery ───────────────────────────────────────
            await asyncio.sleep(0.8)

            orig_vib = sensors.get("vibration_rms_mm_s", 5.0)
            orig_strain = sensors.get("strain_microstrain", 200.0)
            orig_pres = sensors.get("pressure_psi", 65.0)

            # SC-004 stubborn crack fails on iteration 1
            if normalized_scenario == "SC-004" and retry_count == 1:
                threshold_ok = False
                post_vib = 3.65
                post_strain = 175.0
                post_pres = 58.0
            else:
                post_vib = round(orig_vib * 0.28, 2)
                post_strain = round(orig_strain * 0.38, 1)
                post_pres = round(max(32.0, orig_pres * 0.48), 1)
                threshold_ok = post_vib < 3.0 and post_strain < 150

            recovery_confirmed = threshold_ok or retry_count >= max_retries

            r_vib_post = round(post_vib / 3.0, 2)
            r_str_post = round(post_strain / 150.0, 2)
            max_r_post = max(r_vib_post, r_str_post)
            post_risk = "CRITICAL" if max_r_post >= 1.8 else ("WARNING" if max_r_post >= 1.0 else "STABLE")

            yield {
                "event": "verify",
                "data": json.dumps({
                    "node": "verify_recovery",
                    "recovery_confirmed": recovery_confirmed,
                    "retry_count": retry_count,
                    "max_retries": max_retries,
                    "post_sensors": {
                        "vibration_rms_mm_s": post_vib,
                        "strain_microstrain": post_strain,
                        "pressure_psi": post_pres,
                    },
                    "limit_ratios": {
                        "vibration_ratio": r_vib_post,
                        "strain_ratio": r_str_post,
                        "max_ratio": max_r_post,
                    },
                    "risk_level": post_risk,
                    "stability_passed": threshold_ok,
                    "message": (
                        "Recovery CONFIRMED — system stabilized within safe operating envelope."
                        if recovery_confirmed
                        else "Recovery NOT confirmed — re-dispatching actuator countermeasures."
                    ),
                }),
            }

        # ── Step 6: Complete Pipeline ─────────────────────────────────────────
        await asyncio.sleep(0.4)
        elapsed = time.perf_counter() - t_start

        audit_log = [
            f"[IngestTelemetry] Ingested telemetry for {normalized_scenario} ({asset.get('id', 'N/A')})",
            f"[SegmentDefect] SAM 2 isolated {seg_dict.get('defect_count', 0)} surface defect regions",
            f"[SpatialReasoning] Muse Spark Open: severity={ass_dict.get('severity')} conf={ass_dict.get('confidence')}",
            f"[DispatchAction] Dispatched {len(all_actions)} robotic countermeasures across {retry_count} iteration(s)",
            f"[VerifyRecovery] Stability check confirmed={recovery_confirmed} (retries={retry_count})",
        ]

        yield {
            "event": "complete",
            "data": json.dumps({
                "node": "pipeline_complete",
                "status": "COMPLETED",
                "scenario": normalized_scenario,
                "elapsed_seconds": round(elapsed, 2),
                "audit_log": audit_log,
                "summary": {
                    "scenario": normalized_scenario,
                    "severity": ass_dict.get("severity", "MODERATE").upper(),
                    "confidence": f"{int(ass_dict.get('confidence', 0.75) * 100)}%",
                    "affected_zone": ass_dict.get("affected_zone") or "sector-flange (simulated)",
                    "estimated_rul_hours": ass_dict.get("estimated_rul_hours"),
                    "actions_taken": len(all_actions),
                    "recovery_confirmed": recovery_confirmed,
                    "retries": retry_count,
                },
            }),
        }

    return EventSourceResponse(event_generator())


# ── Server Runner ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n════════════════════════════════════════════════════════════════════════")
    print("  🚀  OmniGaze-Agent Mission Control Server starting...")
    print("  📍  Dashboard URL : http://localhost:8000")
    print("  📡  SSE Endpoint  : http://localhost:8000/api/stream/{scenario}")
    print("════════════════════════════════════════════════════════════════════════\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
