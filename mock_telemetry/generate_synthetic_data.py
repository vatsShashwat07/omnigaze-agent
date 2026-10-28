"""
generate_synthetic_data.py
─────────────────────────
Creates a realistic synthetic infrastructure inspection image with visible
surface defects (cracks, corrosion patches) and a companion telemetry JSON
file containing simulated sensor readings.

The generated artefacts live in ``mock_telemetry/`` so the agent graph can
consume them without any external data dependency.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
IMAGE_OUT = _HERE / "synthetic_defect.png"
TELEMETRY_OUT = _HERE / "telemetry_log.json"

# ── Reproducibility seed ──────────────────────────────────────────────────────
RNG = random.Random(42)
NP_RNG = np.random.RandomState(42)


# ─────────────────────────────────────────────────────────────────────────────
# Image Generation
# ─────────────────────────────────────────────────────────────────────────────

def _concrete_background(width: int = 640, height: int = 480) -> np.ndarray:
    """Generate a concrete-like textured background using Perlin-ish noise."""
    base = NP_RNG.randint(150, 180, (height, width), dtype=np.uint8)
    # Multi-scale noise for a realistic concrete look
    for scale in (3, 7, 15):
        noise = NP_RNG.randint(-scale, scale + 1, (height, width), dtype=np.int16)
        base = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    # Slight Gaussian blur for realism
    base = cv2.GaussianBlur(base, (5, 5), 0)
    # Convert to BGR so we can draw coloured defects later
    return cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)


def _draw_crack(img: np.ndarray) -> dict[str, Any]:
    """Draw a jagged crack across a region of the image and return metadata."""
    h, w = img.shape[:2]
    # Random start point in the upper-left quadrant
    x, y = RNG.randint(w // 6, w // 3), RNG.randint(h // 6, h // 3)
    points = [(x, y)]
    length = RNG.randint(120, 220)
    angle = RNG.uniform(-0.3, 0.6)

    for _ in range(length):
        angle += RNG.uniform(-0.25, 0.25)
        dx = int(math.cos(angle) * 3)
        dy = int(math.sin(angle) * 3)
        nx, ny = points[-1][0] + dx, points[-1][1] + dy
        nx = max(0, min(w - 1, nx))
        ny = max(0, min(h - 1, ny))
        points.append((nx, ny))

    # Draw with varying thickness for realism
    pts_arr = np.array(points, dtype=np.int32)
    cv2.polylines(img, [pts_arr], isClosed=False, color=(40, 35, 30), thickness=2)
    cv2.polylines(img, [pts_arr], isClosed=False, color=(60, 55, 50), thickness=1)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
    return {"type": "crack", "bbox_xyxy": bbox, "point_count": len(points)}


def _draw_corrosion(img: np.ndarray) -> dict[str, Any]:
    """Draw an irregular corrosion patch and return metadata."""
    h, w = img.shape[:2]
    cx = RNG.randint(w // 2, int(w * 0.8))
    cy = RNG.randint(h // 2, int(h * 0.85))
    axes = (RNG.randint(30, 60), RNG.randint(20, 45))
    angle = RNG.randint(0, 180)

    # Rust-coloured fill
    overlay = img.copy()
    cv2.ellipse(overlay, (cx, cy), axes, angle, 0, 360, (45, 75, 160), -1)
    alpha = 0.55
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

    # Darker speckles inside the patch
    for _ in range(80):
        ox = int(NP_RNG.normal(cx, axes[0] * 0.4))
        oy = int(NP_RNG.normal(cy, axes[1] * 0.4))
        r = RNG.randint(1, 3)
        colour = (
            RNG.randint(20, 60),
            RNG.randint(40, 90),
            RNG.randint(100, 180),
        )
        cv2.circle(img, (ox, oy), r, colour, -1)

    bbox = [cx - axes[0], cy - axes[1], cx + axes[0], cy + axes[1]]
    bbox = [max(0, int(v)) for v in bbox]
    return {"type": "corrosion", "bbox_xyxy": bbox, "center": [cx, cy]}


def generate_synthetic_image(
    width: int = 640,
    height: int = 480,
    out_path: Path | str = IMAGE_OUT,
    scenario_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Create and save a synthetic infrastructure image with defects.

    Returns
    -------
    tuple[str, list[dict]]
        Absolute path to saved image and a list of defect metadata dicts.
    """
    img = _concrete_background(width, height)
    defects: list[dict[str, Any]] = []

    scenario = (scenario_id or "").upper()
    if scenario == "SC-001":
        # Critical Crack only
        defects.append(_draw_crack(img))
    elif scenario == "SC-002":
        # Corrosion only
        defects.append(_draw_corrosion(img))
    elif scenario == "SC-003":
        # Nominal - no major defect, pristine concrete
        pass
    elif scenario == "SC-004":
        # Stubborn Crack + Corrosion
        defects.append(_draw_crack(img))
        defects.append(_draw_corrosion(img))
    else:
        # Default fallback
        defects.append(_draw_crack(img))
        defects.append(_draw_corrosion(img))

    # Add a subtle grid pattern simulating wall panel joints
    for gx in range(0, width, width // 4):
        cv2.line(img, (gx, 0), (gx, height), (140, 140, 140), 1)
    for gy in range(0, height, height // 3):
        cv2.line(img, (0, gy), (width, gy), (140, 140, 140), 1)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)
    print(f"  [synth] Saved inspection image -> {out_path}")
    return str(out_path.resolve()), defects


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_telemetry(
    defect_meta: list[dict[str, Any]],
    image_path: str,
    out_path: Path | str = TELEMETRY_OUT,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Generate a synthetic telemetry JSON payload and persist it.

    Returns the telemetry dict.
    """
    scenario = (scenario_id or "").upper()

    if scenario == "SC-001":
        sensors = {
            "pressure_psi": 88.5,
            "strain_microstrain": 342.0,
            "vibration_rms_mm_s": 7.95,
            "temperature_c": 39.4,
            "humidity_pct": 68.2,
            "acoustic_emission_db": 68.5,
        }
        asset_condition = "critical_transverse_shear_crack"
    elif scenario == "SC-002":
        sensors = {
            "pressure_psi": 58.0,
            "strain_microstrain": 195.0,
            "vibration_rms_mm_s": 3.82,
            "temperature_c": 41.5,
            "humidity_pct": 89.0,
            "acoustic_emission_db": 44.2,
        }
        asset_condition = "active_surface_corrosion"
    elif scenario == "SC-003":
        sensors = {
            "pressure_psi": 38.0,
            "strain_microstrain": 72.0,
            "vibration_rms_mm_s": 1.15,
            "temperature_c": 22.4,
            "humidity_pct": 51.0,
            "acoustic_emission_db": 28.0,
        }
        asset_condition = "nominal_baseline_health"
    elif scenario == "SC-004":
        sensors = {
            "pressure_psi": 76.5,
            "strain_microstrain": 288.0,
            "vibration_rms_mm_s": 6.45,
            "temperature_c": 33.2,
            "humidity_pct": 72.5,
            "acoustic_emission_db": 59.5,
        }
        asset_condition = "stubborn_propagating_stress_fracture"
    else:
        sensors = {
            "pressure_psi": round(RNG.uniform(35.0, 85.0), 1),
            "vibration_rms_mm_s": round(RNG.uniform(1.2, 8.5), 2),
            "temperature_c": round(RNG.uniform(18.0, 42.0), 1),
            "humidity_pct": round(RNG.uniform(55.0, 95.0), 1),
            "strain_microstrain": round(RNG.uniform(50, 350), 1),
            "acoustic_emission_db": round(RNG.uniform(30, 72), 1),
        }
        asset_condition = "standard_inspection_cycle"

    telemetry: dict[str, Any] = {
        "inspection_id": scenario_id or str(uuid.uuid4()),
        "scenario": scenario_id or "default",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset": {
            "id": f"STRUCTURE-INFRA-{scenario_id or 'SIM'} (simulated)",
            "type": "reinforced_concrete_beam",
            "condition": asset_condition,
            "location": {
                "lat": 37.7749,
                "lon": -122.4194,
                "elevation_m": 12.5,
            },
        },
        "sensors": sensors,
        "visual_frame": {
            "path": image_path,
            "resolution": "640x480",
            "capture_device": "DJI-Mavic3-IR",
        },
        "defect_annotations_ground_truth": defect_meta,
        "status": "pending_inspection",
    }

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(telemetry, fh, indent=2, default=str)
    print(f"  [synth] Saved telemetry log    -> {out_path}")
    return telemetry


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry
# ─────────────────────────────────────────────────────────────────────────────

def run(scenario: str | None = None) -> dict[str, Any]:
    """Generate or reuse existing synthetic artefacts and return the telemetry dict."""
    if IMAGE_OUT.exists() and TELEMETRY_OUT.exists():
        try:
            with open(TELEMETRY_OUT, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
            req_scenario = (scenario or "").upper()
            curr_scenario = (existing.get("scenario") or "").upper()
            if not req_scenario or req_scenario == curr_scenario or existing.get("inspection_id") == scenario:
                print(f"\n[*] Using existing synthetic data (scenario: {scenario or curr_scenario}) ...")
                return existing
        except Exception:
            pass

    # Re-seed with fixed seeds for deterministic generation
    global RNG, NP_RNG
    RNG = random.Random(42)
    NP_RNG = np.random.RandomState(42)

    print(f"\n[*] Generating synthetic inspection data{f' (scenario: {scenario})' if scenario else ''} ...")
    image_path, defect_meta = generate_synthetic_image(scenario_id=scenario)
    telemetry = generate_telemetry(defect_meta, image_path, scenario_id=scenario)
    print("[OK] Synthetic data ready.\n")
    return telemetry


if __name__ == "__main__":
    run()
