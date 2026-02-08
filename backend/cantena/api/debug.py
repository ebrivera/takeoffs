"""Debug visualization endpoint for geometry analysis."""

from __future__ import annotations

import base64
import io
import logging
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debug")


@router.post("/geometry", response_model=None)
async def debug_geometry(
    file: UploadFile,
    output: str = "png",
) -> Response:
    """Analyze PDF geometry and return debug visualization.

    Parameters
    ----------
    file
        PDF file to analyze.
    output
        Response format: "png" returns raw PNG image,
        "json" returns JSON with base64 PNG + measurements.
        Default: "png".
    """
    import fitz  # type: ignore[import-untyped]
    from PIL import Image, ImageDraw

    from cantena.geometry.extractor import VectorExtractor
    from cantena.geometry.measurement import MeasurementService
    from cantena.geometry.scale import ScaleDetector
    from cantena.geometry.walls import WallDetector

    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF files are accepted.",
        )

    content = await file.read()

    # Save to temp file and open with PyMuPDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(content)

    try:

        doc: fitz.Document = fitz.open(tmp_path)
        if doc.page_count == 0:
            raise HTTPException(
                status_code=400,
                detail="PDF has no pages.",
            )

        page: fitz.Page = doc[0]

        # Run geometry pipeline
        extractor = VectorExtractor()
        scale_detector = ScaleDetector()
        wall_detector = WallDetector()
        measurement_svc = MeasurementService(
            extractor, scale_detector, wall_detector,
        )

        measurements = measurement_svc.measure(page)
        drawing_data = measurements.raw_data
        stats = extractor.get_stats(drawing_data)
        wall_analysis = wall_detector.detect(drawing_data)

        # Render base image from PDF
        zoom = 2.0  # 144 DPI
        mat = fitz.Matrix(zoom, zoom)
        pix: fitz.Pixmap = page.get_pixmap(matrix=mat)
        base_img = Image.frombytes(
            "RGB", (pix.width, pix.height), pix.samples,
        ).convert("RGBA")

        # Create a transparent overlay for semi-transparent fills
        overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw room polygons if available
        if measurements.rooms:
            _draw_room_overlays(draw, measurements.rooms, zoom)
        else:
            # Fallback: draw outer boundary in blue (no rooms detected)
            if wall_analysis.outer_boundary:
                boundary_pts = [
                    (p.x * zoom, p.y * zoom)
                    for p in wall_analysis.outer_boundary
                ]
                if len(boundary_pts) >= 3:
                    draw.polygon(
                        boundary_pts,
                        outline=(0, 0, 255, 255),
                        width=2,
                    )

        # Composite overlay onto base image
        base_img = Image.alpha_composite(base_img, overlay)

        # Draw walls and info badge on the composited image
        draw_final = ImageDraw.Draw(base_img)

        # Draw detected walls in red (on top of room fills)
        for seg in wall_analysis.segments:
            x1 = seg.start.x * zoom
            y1 = seg.start.y * zoom
            x2 = seg.end.x * zoom
            y2 = seg.end.y * zoom
            draw_final.line(
                [(x1, y1), (x2, y2)],
                fill=(255, 0, 0, 255),
                width=3,
            )

        # Add text overlay: area, scale, confidence
        _draw_info_badge(draw_final, measurements, base_img.width)

        doc.close()

        # Encode PNG (convert back to RGB for smaller file size)
        final_img = base_img.convert("RGB")
        png_buf = io.BytesIO()
        final_img.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        # Build JSON measurements
        measurements_json = _measurements_to_dict(
            measurements, stats, wall_analysis,
        )

        if output == "json":
            return JSONResponse({
                "image_base64": base64.b64encode(png_bytes).decode(),
                "measurements": measurements_json,
            })

        # Default: return raw PNG
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "X-Geometry-Measurements": "true",
            },
        )

    finally:
        tmp_path = Path(tmp.name)
        if tmp_path.exists():
            tmp_path.unlink()


# Semi-transparent room fill colors (R, G, B, A).
_ROOM_COLORS: list[tuple[int, int, int, int]] = [
    (0, 180, 255, 60),    # cyan
    (255, 180, 0, 60),    # amber
    (0, 220, 80, 60),     # green
    (200, 80, 255, 60),   # purple
    (255, 80, 80, 60),    # red
    (80, 200, 200, 60),   # teal
    (255, 200, 80, 60),   # gold
    (150, 150, 255, 60),  # periwinkle
]

_GRAY_FILL: tuple[int, int, int, int] = (160, 160, 160, 60)


def _draw_room_overlays(
    draw: Any,
    rooms: list[Any],
    zoom: float,
) -> None:
    """Draw semi-transparent room polygon fills with labels and areas."""
    from PIL import ImageFont

    try:
        font = ImageFont.load_default(size=12)
    except TypeError:
        font = ImageFont.load_default()

    for room in rooms:
        scaled_pts = [
            (x * zoom, y * zoom) for x, y in room.polygon_pts
        ]
        if len(scaled_pts) < 3:
            continue

        # Choose fill color
        if room.label is not None:
            color_idx = room.room_index % len(_ROOM_COLORS)
            fill = _ROOM_COLORS[color_idx]
        else:
            fill = _GRAY_FILL

        draw.polygon(scaled_pts, fill=fill, outline=fill[:3])

        # Draw label at centroid
        cx = room.centroid.x * zoom
        cy = room.centroid.y * zoom

        label_text = room.label if room.label is not None else "?"
        area_text = (
            f"{room.area_sf:,.0f} SF" if room.area_sf is not None else ""
        )

        draw.text((cx, cy), label_text, fill=(0, 0, 0), font=font, anchor="mm")
        if area_text:
            draw.text(
                (cx, cy + 14),
                area_text,
                fill=(0, 0, 0),
                font=font,
                anchor="mm",
            )


def _draw_info_badge(
    draw: Any,
    measurements: Any,
    img_width: int,
) -> None:
    """Draw info badge with area, scale, and confidence."""
    lines: list[str] = []

    if measurements.scale is not None:
        lines.append(f"Scale: {measurements.scale.notation}")

    if measurements.gross_area_sf is not None:
        lines.append(f"Area: {measurements.gross_area_sf:,.0f} SF")

    if measurements.building_perimeter_lf is not None:
        lines.append(
            f"Perimeter: {measurements.building_perimeter_lf:,.0f} LF"
        )

    if measurements.total_wall_length_lf is not None:
        lines.append(
            f"Wall length: {measurements.total_wall_length_lf:,.0f} LF"
        )

    lines.append(f"Walls: {measurements.wall_count}")
    lines.append(f"Confidence: {measurements.confidence.value.upper()}")

    # Draw background rectangle
    padding = 10
    line_height = 16
    badge_h = len(lines) * line_height + padding * 2
    badge_w = 280
    x0 = img_width - badge_w - padding
    y0 = padding

    draw.rectangle(
        [(x0, y0), (x0 + badge_w, y0 + badge_h)],
        fill=(0, 0, 0, 180),
    )

    # Draw text lines
    from PIL import ImageFont

    try:
        font = ImageFont.load_default(size=13)
    except TypeError:
        # Older Pillow versions don't accept size param
        font = ImageFont.load_default()

    for i, line in enumerate(lines):
        # Confidence badge color
        color = (255, 255, 255)
        if "Confidence:" in line:
            conf = measurements.confidence.value
            if conf == "high":
                color = (0, 255, 0)
            elif conf == "medium":
                color = (255, 255, 0)
            elif conf == "low":
                color = (255, 165, 0)
            else:
                color = (255, 0, 0)

        draw.text(
            (x0 + padding, y0 + padding + i * line_height),
            line,
            fill=color,
            font=font,
        )


def _measurements_to_dict(
    measurements: Any,
    stats: Any,
    wall_analysis: Any,
) -> dict[str, Any]:
    """Convert measurement results to JSON-serializable dict."""
    scale_dict: dict[str, Any] | None = None
    if measurements.scale is not None:
        scale_dict = {
            "drawing_units": measurements.scale.drawing_units,
            "real_units": measurements.scale.real_units,
            "scale_factor": measurements.scale.scale_factor,
            "notation": measurements.scale.notation,
            "confidence": measurements.scale.confidence.value,
        }

    wall_segments = [
        {
            "start": {"x": seg.start.x, "y": seg.start.y},
            "end": {"x": seg.end.x, "y": seg.end.y},
            "thickness_pts": seg.thickness_pts,
            "orientation": seg.orientation.value,
            "length_pts": seg.length_pts,
        }
        for seg in wall_analysis.segments
    ]

    stats_dict = asdict(stats)

    # Serialize detected rooms
    rooms_list: list[dict[str, Any]] = []
    if measurements.rooms:
        for room in measurements.rooms:
            rooms_list.append({
                "room_index": room.room_index,
                "label": room.label,
                "area_sf": room.area_sf,
                "perimeter_lf": room.perimeter_lf,
                "polygon_vertices": [
                    {"x": x, "y": y} for x, y in room.polygon_pts
                ],
                "centroid": {
                    "x": room.centroid.x,
                    "y": room.centroid.y,
                },
            })

    # Serialize LLM interpretation if available
    llm_dict: dict[str, Any] | None = None
    if measurements.llm_interpretation is not None:
        interp = measurements.llm_interpretation
        llm_dict = {
            "building_type": interp.building_type,
            "structural_system": interp.structural_system,
            "rooms": [
                {
                    "room_index": r.room_index,
                    "confirmed_label": r.confirmed_label,
                    "room_type_enum": r.room_type_enum,
                    "notes": r.notes,
                }
                for r in interp.rooms
            ],
            "special_conditions": interp.special_conditions,
            "measurement_flags": interp.measurement_flags,
            "confidence_notes": interp.confidence_notes,
        }

    result: dict[str, Any] = {
        "scale": scale_dict,
        "gross_area_sf": measurements.gross_area_sf,
        "building_perimeter_lf": measurements.building_perimeter_lf,
        "total_wall_length_lf": measurements.total_wall_length_lf,
        "wall_count": measurements.wall_count,
        "confidence": measurements.confidence.value,
        "wall_segments": wall_segments,
        "stats": stats_dict,
        "rooms": rooms_list,
    }

    if llm_dict is not None:
        result["llm_interpretation"] = llm_dict

    return result
