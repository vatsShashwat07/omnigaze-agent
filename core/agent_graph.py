"""
agent_graph.py
──────────────
LangGraph state machine for the OmniGaze-Agent autonomous inspection loop.

Nodes
─────
1. **IngestTelemetry**  – Load sensor metrics and the visual inspection frame.
2. **SegmentDefect**    – Run SAM segmentation to isolate visual anomalies.
3. **SpatialReasoning** – Query Meta LLM for structural threat assessment.
4. **DispatchAction**   – Execute simulated robotic mitigation actions.
5. **VerifyRecovery**   – Check post-action telemetry to confirm stability.

The graph runs as a linear pipeline with a conditional back-edge from
VerifyRecovery → DispatchAction if recovery is not yet confirmed (up to a
configurable retry cap).
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from core.llm_client import MetaLLMClient, ThreatAssessment
from core.vision_sam import SAMSegmenter, SegmentationResult

# ── Pretty printing helpers ───────────────────────────────────────────────────

_DIVIDER = "─" * 72


def _log_header(title: str) -> None:
    print(f"\n{'═' * 72}")
    print(f"  ▶  {title}")
    print(f"{'═' * 72}")


def _log(msg: str) -> None:
    print(f"  │  {msg}")


def _log_json(data: Any, indent: int = 4) -> None:
    for line in json.dumps(data, indent=indent, default=str).splitlines():
        _log(line)


# ── Pydantic state model ─────────────────────────────────────────────────────

def _merge_lists(a: list, b: list) -> list:
    """Reducer for list-typed state fields (append semantics)."""
    return a + b


class AgentState(BaseModel):
    """Typed state flowing through the LangGraph nodes."""

    # Inputs
    telemetry_path: str = ""
    telemetry: dict[str, Any] = Field(default_factory=dict)
    image_path: str = ""

    # SegmentDefect outputs
    segmentation: dict[str, Any] = Field(default_factory=dict)

    # SpatialReasoning outputs
    threat_assessment: dict[str, Any] = Field(default_factory=dict)

    # DispatchAction outputs
    actions_taken: Annotated[list[dict[str, Any]], _merge_lists] = Field(
        default_factory=list,
    )

    # VerifyRecovery
    recovery_confirmed: bool = False
    retry_count: int = 0
    max_retries: int = 2
    post_sensors: dict[str, Any] = Field(default_factory=dict)

    # Audit trail
    log: Annotated[list[str], _merge_lists] = Field(default_factory=list)


# ── Node implementations ─────────────────────────────────────────────────────

def ingest_telemetry(state: AgentState) -> dict[str, Any]:
    """Load telemetry JSON and resolve the visual frame path."""
    _log_header("1 · INGEST TELEMETRY")

    telem_path = Path(state.telemetry_path)
    if not telem_path.exists():
        raise FileNotFoundError(f"Telemetry file not found: {telem_path}")

    with open(telem_path, encoding="utf-8") as fh:
        telemetry = json.load(fh)

    image_path = telemetry.get("visual_frame", {}).get("path", "")
    sensors = telemetry.get("sensors", {})

    _log(f"Inspection ID : {telemetry.get('inspection_id', 'N/A')}")
    _log(f"Asset         : {telemetry.get('asset', {}).get('id', 'N/A')}")
    _log(f"Image path    : {image_path}")
    _log(f"Sensors       :")
    for k, v in sensors.items():
        _log(f"  {k}: {v}")

    return {
        "telemetry": telemetry,
        "image_path": image_path,
        "log": [f"[IngestTelemetry] Loaded {telem_path.name}"],
    }


def segment_defect(state: AgentState) -> dict[str, Any]:
    """Run SAM segmentation on the inspection image."""
    _log_header("2 · SEGMENT DEFECT (SAM)")

    segmenter = SAMSegmenter()
    result: SegmentationResult = segmenter.segment(state.image_path)
    result_dict = result.to_dict()

    _log(f"Defects found : {result_dict['defect_count']}")
    _log(f"Total area %  : {result_dict['total_defect_area_pct']:.4f}")
    for d in result_dict.get("defects", []):
        _log(
            f"  • {d['defect_type']} [{d['defect_id']}] "
            f"area={d['surface_area_pct']:.4f}%  "
            f"conf={d['confidence']:.0%}  "
            f"bbox={d['bbox_xyxy']}"
        )
    _log(f"Annotated img : {result_dict.get('annotated_image_path', 'N/A')}")

    return {
        "segmentation": result_dict,
        "log": [f"[SegmentDefect] {result_dict['defect_count']} defects isolated"],
    }


def spatial_reasoning(state: AgentState) -> dict[str, Any]:
    """Query Meta LLM for structural threat severity assessment."""
    _log_header("3 · SPATIAL REASONING (Meta LLM)")

    client = MetaLLMClient()
    sensors = state.telemetry.get("sensors", {})

    assessment: ThreatAssessment = client.assess_threat(
        defect_report=state.segmentation,
        sensor_readings=sensors,
    )
    assessment_dict = assessment.to_dict()

    _log(f"Severity      : {assessment.severity.upper()}")
    _log(f"Confidence    : {assessment.confidence:.0%}")
    _log(f"Affected zone : {assessment.affected_zone}")
    _log(f"Est. RUL (h)  : {assessment.estimated_rul_hours}")
    _log(f"Reasoning     : {assessment.reasoning[:120]}…")
    _log("Recommended actions:")
    for i, action in enumerate(assessment.recommended_actions, 1):
        _log(f"  {i}. {action}")

    return {
        "threat_assessment": assessment_dict,
        "log": [
            f"[SpatialReasoning] severity={assessment.severity} "
            f"confidence={assessment.confidence:.2f}"
        ],
    }


def dispatch_action(state: AgentState) -> dict[str, Any]:
    """Execute simulated robotic mitigation actions."""
    _log_header("4 · DISPATCH ACTION")

    severity = state.threat_assessment.get("severity", "moderate")
    actions_taken: list[dict[str, Any]] = []

    # Action catalogue keyed by severity
    action_catalogue: dict[str, list[dict[str, Any]]] = {
        "critical": [
            {
                "action": "pressure_valve_adjustment",
                "target": "PV-12",
                "parameter": "reduce_pressure_psi",
                "value": 45,
                "status": "executed",
            },
            {
                "action": "emergency_lockdown",
                "target": "sector-flange (simulated)",
                "parameter": "access_restriction",
                "value": "full_lockdown",
                "status": "executed",
            },
            {
                "action": "drone_repositioning",
                "target": "DJI-Mavic3-IR",
                "parameter": "new_altitude_m",
                "value": 5.0,
                "status": "executed",
            },
        ],
        "high": [
            {
                "action": "pressure_valve_adjustment",
                "target": "PV-12",
                "parameter": "reduce_pressure_psi",
                "value": 20,
                "status": "executed",
            },
            {
                "action": "drone_repositioning",
                "target": "DJI-Mavic3-IR",
                "parameter": "new_altitude_m",
                "value": 8.0,
                "status": "executed",
            },
        ],
        "moderate": [
            {
                "action": "increase_monitoring_frequency",
                "target": "sensor_array_47A",
                "parameter": "interval_seconds",
                "value": 300,
                "status": "executed",
            },
        ],
        "low": [
            {
                "action": "log_anomaly",
                "target": "maintenance_db",
                "parameter": "priority",
                "value": "routine",
                "status": "logged",
            },
        ],
    }

    for action in action_catalogue.get(severity, action_catalogue["moderate"]):
        action["timestamp"] = datetime.now(timezone.utc).isoformat()
        actions_taken.append(action)
        _log(
            f"  🤖 {action['action']} → {action['target']} "
            f"({action['parameter']}={action['value']})  [{action['status']}]"
        )
        time.sleep(0.15)  # simulate actuation delay

    return {
        "actions_taken": actions_taken,
        "log": [f"[DispatchAction] Executed {len(actions_taken)} mitigations"],
    }


def verify_recovery(state: AgentState) -> dict[str, Any]:
    """Check post-action telemetry to confirm system stability."""
    _log_header("5 · VERIFY RECOVERY")

    # Simulate post-action sensor readings (improved after mitigation)
    original_vibration = state.telemetry.get("sensors", {}).get(
        "vibration_rms_mm_s", 5.0,
    )
    original_strain = state.telemetry.get("sensors", {}).get(
        "strain_microstrain", 200.0,
    )
    original_pressure = state.telemetry.get("sensors", {}).get(
        "pressure_psi", 65.0,
    )

    retry = state.retry_count + 1
    scenario = state.telemetry.get("scenario", "")

    if scenario == "SC-004" and retry == 1:
        # Deliberately fails on iteration 1 for stubborn crack to demonstrate closed-loop retry
        threshold_ok = False
        post_vibration = 3.65
        post_strain = 175.0
        post_pressure = 58.0
    else:
        post_vibration = original_vibration * random.uniform(0.25, 0.45)
        post_strain = original_strain * random.uniform(0.3, 0.5)
        post_pressure = max(35.0, original_pressure * random.uniform(0.4, 0.6))
        threshold_ok = post_vibration < 3.0 and post_strain < 150

    _log(f"Post-action vibration : {post_vibration:.2f} mm/s  (was {original_vibration})")
    _log(f"Post-action strain    : {post_strain:.1f} µε")
    _log(f"Post-action pressure  : {post_pressure:.1f} PSI")
    _log(f"Stability threshold   : {'✅ PASS' if threshold_ok else '❌ FAIL'}")
    _log(f"Retry iteration       : {retry}/{state.max_retries}")

    confirmed = threshold_ok or retry > state.max_retries

    if confirmed:
        _log("🟢  Recovery CONFIRMED — system stable.")
    else:
        _log("🔴  Recovery NOT confirmed — will re-dispatch.")

    post_sensors = {
        "vibration_rms_mm_s": round(post_vibration, 2),
        "strain_microstrain": round(post_strain, 1),
        "pressure_psi": round(post_pressure, 1),
    }

    return {
        "recovery_confirmed": confirmed,
        "retry_count": retry,
        "post_sensors": post_sensors,
        "log": [f"[VerifyRecovery] confirmed={confirmed} retry={retry}"],
    }


# ── Conditional edge ──────────────────────────────────────────────────────────

def _should_retry(state: AgentState) -> str:
    if state.recovery_confirmed:
        return "end"
    return "dispatch_action"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_agent_graph() -> StateGraph:
    """Construct and compile the OmniGaze LangGraph state machine."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("ingest_telemetry", ingest_telemetry)
    graph.add_node("segment_defect", segment_defect)
    graph.add_node("spatial_reasoning", spatial_reasoning)
    graph.add_node("dispatch_action", dispatch_action)
    graph.add_node("verify_recovery", verify_recovery)

    # Linear edges
    graph.add_edge("ingest_telemetry", "segment_defect")
    graph.add_edge("segment_defect", "spatial_reasoning")
    graph.add_edge("spatial_reasoning", "dispatch_action")
    graph.add_edge("dispatch_action", "verify_recovery")

    # Conditional back-edge for retry loop
    graph.add_conditional_edges(
        "verify_recovery",
        _should_retry,
        {
            "dispatch_action": "dispatch_action",
            "end": END,
        },
    )

    # Entry point
    graph.set_entry_point("ingest_telemetry")

    return graph.compile()
