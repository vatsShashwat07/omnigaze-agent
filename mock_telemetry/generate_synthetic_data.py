"""
generate_synthetic_data.py
─────────────────────────
Creates authentic infrastructure inspection telemetry and links high-resolution
real industrial defect images (or synthetic fallback frames) with simulated sensor
readings.

The generated artefacts live in ``mock_telemetry/`` so the agent graph and SSE server
can consume them without any external data dependency.
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

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
IMAGE_OUT = _HERE / "synthetic_defect.png"
TELEMETRY_OUT = _HERE / "telemetry_log.json"

# ── Real Industrial Defect Assets Map ─────────────────────────────────────────
REAL_ASSET_MAP: dict[str, dict[str, Any]] = {
    "SC-001": {
        "rel_path": "mock_telemetry/real_assets/bridge_girder_shear_crack.png",
        "asset_id": "STRUCTURE-INFRA-SC-001 (simulated)",
        "asset_type": "steel_concrete_bridge_girder",
        "condition": "critical_transverse_shear_crack",
        "resolution": "1200x896",
        "device": "DJI-Mavic3-IR",
        "ground_truth": [{"type": "crack", "bbox_xyxy": [80, 0, 1067, 865], "point_count": 124}],
    },
    "SC-002": {
        "rel_path": "mock_telemetry/real_assets/pipeline_pitting_corrosion.png",
        "asset_id": "STRUCTURE-INFRA-SC-002 (simulated)",
        "asset_type": "industrial_carbon_steel_pipeline",
        "condition": "active_surface_pitting_corrosion",
        "resolution": "1200x896",
        "device": "FLIR-Optical-Cam-4k",
        "ground_truth": [{"type": "corrosion", "bbox_xyxy": [0, 159, 1173, 896], "point_count": 96}],
    },
    "SC-004": {
        "rel_path": "mock_telemetry/real_assets/weld_joint_fatigue_crack.png",
        "asset_id": "STRUCTURE-INFRA-SC-004 (simulated)",
        "asset_type": "welded_structural_steel_joint",
        "condition": "stubborn_propagating_fatigue_crack",
        "resolution": "1200x896",
        "device": "High-Res-Borescope-NDT",
        "ground_truth": [{"type": "crack", "bbox_xyxy": [423, 580, 822, 848], "point_count": 110}],
    },
}

# ── Reproducibility seed ──────────────────────────────────────────────────────
RNG = random.Random(42)
NP_RNG = np.random.RandomState(42)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic Image Fallback (e.g. for SC-003 Nominal or unmapped scenarios)
# ─────────────────────────────────────────────────────────────────────────────

def _concrete_background(width: int = 640, height: int = 480) -> np.ndarray:
    """Generate a concrete-like textured background using multi-scale noise."""
    base = NP_RNG.randint(150, 180, (height, width), dtype=np.uint8)
    for scale in (3, 7, 15):
        noise = NP_RNG.randint(-scale, scale + 1, (height, width), dtype=np.int16)
        base = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    base = cv2.GaussianBlur(base, (5, 5), 0)
    return cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)


def _draw_crack(img: np.ndarray) -> dict[str, Any]:
    """Draw a jagged crack across a region of the image and return metadata."""
    h, w = img.shape[:2]
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

    overlay = img.copy()
    cv2.ellipse(overlay, (cx, cy), axes, angle, 0, 360, (45, 75, 160), -1)
    alpha = 0.55
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

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
    """Create and save a synthetic infrastructure image fallback with defects."""
    img = _concrete_background(width, height)
    defects: list[dict[str, Any]] = []

    scenario = (scenario_id or "").upper()
    if scenario == "SC-001":
        defects.append(_draw_crack(img))
    elif scenario == "SC-002":
        defects.append(_draw_corrosion(img))
    elif scenario == "SC-003":
        pass  # Nominal pristine concrete
    elif scenario == "SC-004":
        defects.append(_draw_crack(img))
        defects.append(_draw_corrosion(img))
    else:
        defects.append(_draw_crack(img))

    for gx in range(0, width, width // 4):
        cv2.line(img, (gx, 0), (gx, height), (140, 140, 140), 1)
    for gy in range(0, height, height // 3):
        cv2.line(img, (0, gy), (width, gy), (140, 140, 140), 1)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)
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
    """Generate a telemetry JSON payload and persist it."""
    scenario = (scenario_id or "SC-001").upper()

    # Match scenario sensors and metadata
    if scenario == "SC-001":
        sensors = {
            "pressure_psi": 88.5,
            "strain_microstrain": 342.0,
            "vibration_rms_mm_s": 7.95,
            "temperature_c": 39.4,
            "humidity_pct": 68.2,
            "acoustic_emission_db": 68.5,
        }
        asset_info = REAL_ASSET_MAP["SC-001"]
    elif scenario == "SC-002":
        sensors = {
            "pressure_psi": 58.0,
            "strain_microstrain": 195.0,
            "vibration_rms_mm_s": 3.82,
            "temperature_c": 41.5,
            "humidity_pct": 89.0,
            "acoustic_emission_db": 44.2,
        }
        asset_info = REAL_ASSET_MAP["SC-002"]
    elif scenario == "SC-003":
        sensors = {
            "pressure_psi": 38.0,
            "strain_microstrain": 72.0,
            "vibration_rms_mm_s": 1.15,
            "temperature_c": 22.4,
            "humidity_pct": 51.0,
            "acoustic_emission_db": 28.0,
        }
        asset_info = {
            "asset_id": "STRUCTURE-INFRA-SC-003 (simulated)",
            "asset_type": "reinforced_concrete_beam",
            "condition": "nominal_baseline_health",
            "resolution": "640x480",
            "device": "DJI-Mavic3-IR",
        }
    elif scenario == "SC-004":
        sensors = {
            "pressure_psi": 76.5,
            "strain_microstrain": 288.0,
            "vibration_rms_mm_s": 6.45,
            "temperature_c": 33.2,
            "humidity_pct": 72.5,
            "acoustic_emission_db": 59.5,
        }
        asset_info = REAL_ASSET_MAP["SC-004"]
    else:
        sensors = {
            "pressure_psi": 55.0,
            "vibration_rms_mm_s": 4.2,
            "temperature_c": 30.0,
            "humidity_pct": 65.0,
            "strain_microstrain": 180.0,
            "acoustic_emission_db": 45.0,
        }
        asset_info = {
            "asset_id": f"STRUCTURE-INFRA-{scenario} (simulated)",
            "asset_type": "reinforced_concrete_beam",
            "condition": "standard_inspection_cycle",
            "resolution": "640x480",
            "device": "DJI-Mavic3-IR",
        }

    telemetry: dict[str, Any] = {
        "inspection_id": scenario,
        "scenario": scenario,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset": {
            "id": asset_info["asset_id"],
            "type": asset_info["asset_type"],
            "condition": asset_info["condition"],
            "location": {
                "lat": 37.7749,
                "lon": -122.4194,
                "elevation_m": 12.5,
            },
        },
        "sensors": sensors,
        "visual_frame": {
            "path": image_path,
            "resolution": asset_info.get("resolution", "1200x896"),
            "capture_device": asset_info.get("device", "DJI-Mavic3-IR"),
        },
        "defect_annotations_ground_truth": defect_meta,
        "status": "pending_inspection",
    }

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(telemetry, fh, indent=2, default=str)
    print(f"  [telemetry] Saved telemetry log -> {out_path} (asset: {image_path})")
    return telemetry


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry
# ─────────────────────────────────────────────────────────────────────────────

def run(scenario: str | None = None) -> dict[str, Any]:
    """Generate or retrieve inspection data mapping authentic real assets for each scenario."""
    req_scenario = (scenario or "SC-001").upper()

    # If the requested scenario maps to a real industrial asset
    if req_scenario in REAL_ASSET_MAP:
        meta = REAL_ASSET_MAP[req_scenario]
        real_img_rel = meta["rel_path"]
        real_img_abs = _PROJECT_ROOT / real_img_rel

        # Verify the real asset image file exists on disk
        if real_img_abs.exists():
            # Check if existing telemetry_log.json matches this scenario and asset
            if TELEMETRY_OUT.exists():
                try:
                    with open(TELEMETRY_OUT, "r", encoding="utf-8") as fh:
                        existing = json.load(fh)
                    if existing.get("scenario") == req_scenario and existing.get("visual_frame", {}).get("path") == real_img_rel:
                        print(f"\n[*] Using existing telemetry with real asset ({real_img_rel}) ...")
                        return existing
                except Exception:
                    pass

            print(f"\n[*] Linking authentic industrial inspection frame for {req_scenario} -> {real_img_rel}")
            telemetry = generate_telemetry(
                defect_meta=meta["ground_truth"],
                image_path=real_img_rel,
                scenario_id=req_scenario,
            )
            return telemetry

    # Fallback to synthetic image generation (e.g. SC-003 or custom)
    print(f"\n[*] Generating inspection data for {req_scenario} ...")
    image_path, defect_meta = generate_synthetic_image(scenario_id=req_scenario)
    rel_image = str(Path(image_path).relative_to(_PROJECT_ROOT)).replace("\\", "/")
    telemetry = generate_telemetry(defect_meta, rel_image, scenario_id=req_scenario)
    return telemetry


if __name__ == "__main__":
    run()
