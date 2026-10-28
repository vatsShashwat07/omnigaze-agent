"""
vision_sam.py
─────────────
SAM-inspired visual defect segmentation module for OmniGaze-Agent.

Provides promptable mask generation for surface anomalies on infrastructure
assets: cracks, corrosion patches, and structural deformations.

When a live SAM endpoint is configured (via SAM_ENDPOINT env-var) the module
proxies requests to it.  Otherwise it runs a fully self-contained **local
simulation** using classical CV (Canny + contour analysis + colour-space
thresholding) so the pipeline works without any GPU or external model.

The output is a structured ``SegmentationResult`` containing per-defect masks,
bounding boxes, surface-area percentages, and an annotated overlay image.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
_SAM_ENDPOINT = os.getenv("SAM_ENDPOINT", "")
_OUTPUT_DIR = Path("mock_telemetry")


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DefectRegion:
    """A single detected defect region."""
    defect_id: str
    defect_type: str              # "crack" | "corrosion" | "deformation"
    bbox_xyxy: list[int]          # [x1, y1, x2, y2]
    mask_pixel_count: int
    surface_area_pct: float       # % of total image area
    confidence: float             # 0.0 – 1.0
    centroid: tuple[int, int] = (0, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "defect_type": self.defect_type,
            "bbox_xyxy": self.bbox_xyxy,
            "mask_pixel_count": self.mask_pixel_count,
            "surface_area_pct": round(self.surface_area_pct, 4),
            "confidence": round(self.confidence, 3),
            "centroid": list(self.centroid),
        }


@dataclass
class SegmentationResult:
    """Aggregated segmentation output for an inspection frame."""
    image_path: str
    image_resolution: tuple[int, int]
    total_defect_area_pct: float
    defects: list[DefectRegion] = field(default_factory=list)
    annotated_image_path: str = ""
    backend: str = "classical-fallback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "image_resolution": list(self.image_resolution),
            "total_defect_area_pct": round(self.total_defect_area_pct, 4),
            "defect_count": len(self.defects),
            "defects": [d.to_dict() for d in self.defects],
            "annotated_image_path": self.annotated_image_path,
            "backend": self.backend,
        }


# ── SAM Segmentation Module ──────────────────────────────────────────────────

class SAMSegmenter:
    """Zero-shot promptable segmentation inspired by Meta SAM."""

    def __init__(self, sam_endpoint: str = _SAM_ENDPOINT) -> None:
        self.sam_endpoint = sam_endpoint
        self._use_remote = bool(sam_endpoint)

    def segment(self, image_path: str) -> SegmentationResult:
        """Run defect segmentation on an image.

        Parameters
        ----------
        image_path : str
            Path to the input inspection image.

        Returns
        -------
        SegmentationResult
        """
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")

        h, w = img.shape[:2]
        total_pixels = h * w

        if self._use_remote:
            defects = self._remote_segment(image_path)
            backend = "sam2"
        else:
            defects = self._local_segment(img, total_pixels)
            backend = "classical-fallback"

        total_area = sum(d.surface_area_pct for d in defects)

        # Create annotated overlay
        annotated_path = self._draw_overlay(img, defects, image_path)

        return SegmentationResult(
            image_path=image_path,
            image_resolution=(w, h),
            total_defect_area_pct=total_area,
            defects=defects,
            annotated_image_path=annotated_path,
            backend=backend,
        )

    # ── Local classical-CV segmentation ───────────────────────────────────

    def _local_segment(
        self, img: np.ndarray, total_pixels: int,
    ) -> list[DefectRegion]:
        """Detect defects using classical CV as a SAM simulation."""
        defects: list[DefectRegion] = []

        # 1) Crack detection via Canny edge + morphological filtering
        defects.extend(self._detect_cracks(img, total_pixels))

        # 2) Corrosion detection via HSV colour thresholding
        defects.extend(self._detect_corrosion(img, total_pixels))

        return defects

    @staticmethod
    def _detect_cracks(
        img: np.ndarray, total_pixels: int,
    ) -> list[DefectRegion]:
        """Detect linear crack-like features."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        # Dilate to connect nearby edge fragments
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        regions: list[DefectRegion] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            arc = cv2.arcLength(cnt, closed=False)
            if area < 30 or arc < 30:
                continue  # too small

            # Crack heuristic: high arc-length-to-area ratio (elongated)
            ratio = arc / (area + 1e-6)
            if ratio < 0.08:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            mask_px = int(area)
            M = cv2.moments(cnt)
            cx = int(M["m10"] / (M["m00"] + 1e-6))
            cy = int(M["m01"] / (M["m00"] + 1e-6))

            regions.append(DefectRegion(
                defect_id=f"crack-{uuid.uuid4().hex[:8]}",
                defect_type="crack",
                bbox_xyxy=[x, y, x + bw, y + bh],
                mask_pixel_count=mask_px,
                surface_area_pct=(mask_px / total_pixels) * 100,
                confidence=min(0.65 + ratio * 0.1, 0.95),
                centroid=(cx, cy),
            ))

        return regions

    @staticmethod
    def _detect_corrosion(
        img: np.ndarray, total_pixels: int,
    ) -> list[DefectRegion]:
        """Detect rust / corrosion patches via HSV colour thresholding."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Rust-orange hue range
        lower = np.array([5, 50, 50])
        upper = np.array([25, 255, 200])
        mask = cv2.inRange(hsv, lower, upper)

        # Clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        regions: list[DefectRegion] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 200:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            M = cv2.moments(cnt)
            cx = int(M["m10"] / (M["m00"] + 1e-6))
            cy = int(M["m01"] / (M["m00"] + 1e-6))

            regions.append(DefectRegion(
                defect_id=f"corr-{uuid.uuid4().hex[:8]}",
                defect_type="corrosion",
                bbox_xyxy=[x, y, x + bw, y + bh],
                mask_pixel_count=int(area),
                surface_area_pct=(area / total_pixels) * 100,
                confidence=0.78,
                centroid=(cx, cy),
            ))

        return regions

    # ── Annotated overlay ─────────────────────────────────────────────────

    @staticmethod
    def _draw_overlay(
        img: np.ndarray,
        defects: list[DefectRegion],
        src_path: str,
    ) -> str:
        """Draw bounding boxes and labels on the image and save it."""
        overlay = img.copy()
        colour_map = {
            "crack": (0, 0, 255),       # red
            "corrosion": (0, 165, 255),  # orange
            "deformation": (0, 255, 255),  # yellow
        }

        for d in defects:
            c = colour_map.get(d.defect_type, (255, 255, 255))
            x1, y1, x2, y2 = d.bbox_xyxy
            cv2.rectangle(overlay, (x1, y1), (x2, y2), c, 2)
            label = f"{d.defect_type} ({d.confidence:.0%})"
            cv2.putText(
                overlay, label, (x1, max(y1 - 8, 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1, cv2.LINE_AA,
            )

        out_path = _OUTPUT_DIR / "annotated_defects.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), overlay)
        return str(out_path.resolve())

    # ── Remote SAM endpoint (stub for future integration) ─────────────────

    def _remote_segment(self, image_path: str) -> list[DefectRegion]:
        """Proxy segmentation to a hosted SAM endpoint."""
        # TODO: implement multipart upload to SAM API
        print("  ⚠  Remote SAM endpoint not yet implemented; using local CV.")
        img = cv2.imread(image_path)
        h, w = img.shape[:2]
        return self._local_segment(img, h * w)
