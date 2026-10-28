#!/usr/bin/env python3
"""
main.py — OmniGaze-Agent CLI
─────────────────────────────
Entry point that:
  1. Generates synthetic inspection data (image + telemetry).
  2. Runs the full LangGraph agent pipeline end-to-end.
  3. Prints a rich formatted summary of every decision and state transition.

Usage
─────
    python main.py                    # default run
    python main.py --telemetry <path> # use an existing telemetry JSON
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows (cp1252 cannot render Unicode box-drawing / emoji)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is on sys.path so `core.*` imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mock_telemetry.generate_synthetic_data import run as generate_data
from core.agent_graph import AgentState, build_agent_graph

# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = r"""
   ____                  _  ____                           _                    _
  / __ \                (_)/ __ \                         / \   __ _  ___ _ __ | |_
 | |  | |_ __ ___  _ __  | |  _| __ _ _______           / _ \ / _` |/ _ \ '_ \| __|
 | |  | | '_ ` _ \| '_ \| | |_ |/ _` |_  / _ \  _____ / ___ \ (_| |  __/ | | | |_
 | |__| | | | | | | | | | |__| | (_| |/ /  __/ |_____/_/   \_\__, |\___|_| |_|\__|
  \____/|_| |_| |_|_| |_|\_____|\___|/___\___|               |___/

  Autonomous Spatial-Visual Infrastructure Inspector
  Cerebral Valley × Meta AI Developer Hackathon 2026
"""


def _print_summary(final_state: dict) -> None:
    """Print a formatted end-of-run summary."""
    print(f"\n{'━' * 72}")
    print("  📋  PIPELINE SUMMARY")
    print(f"{'━' * 72}")

    # Scenario / Inspection
    inspection_id = final_state.get("telemetry", {}).get("inspection_id")
    scenario = final_state.get("telemetry", {}).get("scenario")
    if scenario:
        print(f"  Scenario        : {scenario}")
    if inspection_id:
        print(f"  Inspection ID   : {inspection_id}")

    # Threat assessment
    ta = final_state.get("threat_assessment", {})
    if ta:
        severity = ta.get("severity", "N/A").upper()
        sev_icon = {
            "CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢",
        }.get(severity, "⚪")
        print(f"  Severity        : {sev_icon}  {severity}")
        print(f"  Confidence      : {ta.get('confidence', 0):.0%}")
        print(f"  Affected zone   : {ta.get('affected_zone', 'N/A')}")
        print(f"  Est. RUL (hrs)  : {ta.get('estimated_rul_hours', 'N/A')}")

    # Actions
    actions = final_state.get("actions_taken", [])
    print(f"  Actions taken   : {len(actions)}")
    for a in actions:
        print(f"    • {a['action']} → {a['target']} [{a.get('status', '?')}]")

    # Recovery
    confirmed = final_state.get("recovery_confirmed", False)
    retries = final_state.get("retry_count", 0)
    status_icon = "✅" if confirmed else "❌"
    print(f"  Recovery        : {status_icon}  confirmed={confirmed}  retries={retries}")

    # Audit log
    log = final_state.get("log", [])
    if log:
        print(f"\n  📜  Audit Trail ({len(log)} entries):")
        for entry in log:
            print(f"    {entry}")

    print(f"{'━' * 72}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OmniGaze-Agent — autonomous infrastructure inspector",
    )
    parser.add_argument(
        "--telemetry", type=str, default=None,
        help="Path to an existing telemetry JSON (skips synthetic generation).",
    )
    parser.add_argument(
        "--scenario", type=str, default=None,
        help="Inspection scenario identifier (e.g. SC-004).",
    )
    args = parser.parse_args()

    print(BANNER)

    # ── Step 1: Synthetic data ────────────────────────────────────────────
    if args.telemetry:
        telemetry_path = args.telemetry
        print(f"  Using provided telemetry: {telemetry_path}\n")
    else:
        if args.scenario:
            print(f"  Target scenario: {args.scenario}")
        telemetry = generate_data(scenario=args.scenario)
        telemetry_path = str(
            (Path(__file__).resolve().parent / "mock_telemetry" / "telemetry_log.json")
        )

    # ── Step 2: Build & run the agent graph ───────────────────────────────
    print(f"\n{'═' * 72}")
    print("  🚀  Launching OmniGaze-Agent pipeline …")
    print(f"{'═' * 72}")

    graph = build_agent_graph()

    initial_state = AgentState(telemetry_path=telemetry_path)

    t0 = time.perf_counter()
    final_state = graph.invoke(initial_state)
    elapsed = time.perf_counter() - t0

    # ── Step 3: Summary ───────────────────────────────────────────────────
    _print_summary(final_state)
    print(f"  ⏱  Pipeline completed in {elapsed:.2f}s")
    print("  🏁  OmniGaze-Agent run finished.\n")


if __name__ == "__main__":
    main()
