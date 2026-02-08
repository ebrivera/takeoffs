"""FastAPI application — create_app factory with /api endpoints."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# Load .env from project root (backend/../.env or backend/.env)
_backend_dir = Path(__file__).resolve().parent.parent.parent
_project_root = _backend_dir.parent
load_dotenv(_project_root / ".env")
load_dotenv(_backend_dir / ".env")

from cantena.exceptions import CantenaError
from cantena.models.building import BuildingModel  # noqa: TCH001 (FastAPI resolves at runtime)

if TYPE_CHECKING:
    from cantena.engine import CostEngine
    from cantena.services.pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)


def create_app(
    *,
    pipeline: AnalysisPipeline | None = None,
    cost_engine: CostEngine | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    pipeline
        Optional pre-built pipeline for dependency injection (e.g. tests).
        If not provided, one is created from environment variables on first
        request to /api/analyze.
    cost_engine
        Optional pre-built cost engine for /api/estimate. If not provided,
        one is created via create_default_engine on first request.
    """
    app = FastAPI(title="Cantena", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store on app state so tests can inject mocks
    app.state.pipeline = pipeline
    app.state.cost_engine = cost_engine

    def _get_pipeline() -> AnalysisPipeline:
        pl: AnalysisPipeline | None = app.state.pipeline
        if pl is not None:
            return pl
        # Lazy-create from environment
        from cantena.api.deps import create_pipeline

        pl = create_pipeline()
        app.state.pipeline = pl
        return pl

    def _get_cost_engine() -> CostEngine:
        eng: CostEngine | None = app.state.cost_engine
        if eng is not None:
            return eng
        from cantena.factory import create_default_engine

        eng = create_default_engine()
        app.state.cost_engine = eng
        return eng

    # ------------------------------------------------------------------
    # GET /api/health
    # ------------------------------------------------------------------

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    # ------------------------------------------------------------------
    # POST /api/analyze
    # ------------------------------------------------------------------

    @app.post("/api/analyze")
    async def analyze(
        file: UploadFile,
        project_name: str = Form(...),
        city: str = Form(...),
        state: str = Form(...),
    ) -> dict[str, Any]:
        # Check for API key
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "ANTHROPIC_API_KEY is not configured. "
                    "Try the sample estimate instead."
                ),
            )

        # Validate file type
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF files are accepted.",
            )

        # Save upload to temp file
        tmp_dir = Path(tempfile.mkdtemp(prefix="cantena_"))
        tmp_path = tmp_dir / filename
        try:
            content = await file.read()
            tmp_path.write_bytes(content)

            location = f"{city}, {state}"
            pl = _get_pipeline()
            result = pl.analyze(
                pdf_path=tmp_path,
                project_name=project_name,
                location=location,
            )

            estimate = result.estimate
            return {
                "estimate": estimate.model_dump(mode="json"),
                "building_model": result.analysis.building_model.model_dump(
                    mode="json",
                ),
                "summary_dict": estimate.to_summary_dict(),
                "export_dict": estimate.to_export_dict(),
                "analysis": {
                    "reasoning": result.analysis.reasoning,
                    "warnings": result.analysis.warnings,
                },
                "processing_time_seconds": result.processing_time_seconds,
                "pages_analyzed": result.pages_analyzed,
                "geometry_available": result.geometry_available,
                "measurement_confidence": (
                    result.measurement_confidence.value
                ),
            }

        except CantenaError as exc:
            logger.exception("Pipeline error during analysis")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            # Clean up uploaded temp file
            if tmp_path.exists():
                tmp_path.unlink()
            if tmp_dir.exists():
                tmp_dir.rmdir()

    # ------------------------------------------------------------------
    # POST /api/estimate
    # ------------------------------------------------------------------

    @app.post("/api/estimate")
    def estimate(building: BuildingModel) -> dict[str, Any]:
        engine = _get_cost_engine()
        project_name = (
            f"{building.location.city}, {building.location.state}"
        )
        result = engine.estimate(building, project_name)
        return result.model_dump(mode="json")

    # ------------------------------------------------------------------
    # GET /api/sample-estimate
    # ------------------------------------------------------------------

    @app.get("/api/sample-estimate")
    def sample_estimate() -> dict[str, Any]:
        from cantena.models.building import ComplexityScores, Location
        from cantena.models.enums import (
            BuildingType,
            Confidence,
            ExteriorWall,
            MechanicalSystem,
            StructuralSystem,
        )

        sample_building = BuildingModel(
            building_type=BuildingType.OFFICE_MID_RISE,
            building_use="General office building",
            gross_sf=45000.0,
            stories=3,
            story_height_ft=13.0,
            structural_system=StructuralSystem.STEEL_FRAME,
            exterior_wall_system=ExteriorWall.CURTAIN_WALL,
            mechanical_system=MechanicalSystem.VAV,
            location=Location(city="Baltimore", state="MD"),
            complexity_scores=ComplexityScores(
                structural=3, mep=3, finishes=3, site=2,
            ),
            confidence={
                "building_type": Confidence.HIGH,
                "gross_sf": Confidence.HIGH,
                "stories": Confidence.HIGH,
                "story_height_ft": Confidence.MEDIUM,
                "structural_system": Confidence.HIGH,
                "exterior_wall_system": Confidence.MEDIUM,
            },
        )
        engine = _get_cost_engine()
        est = engine.estimate(sample_building, "Baltimore Office Tower")
        return {
            "estimate": est.model_dump(mode="json"),
            "building_model": sample_building.model_dump(mode="json"),
            "summary_dict": est.to_summary_dict(),
            "export_dict": est.to_export_dict(),
            "analysis": {
                "reasoning": (
                    "This is a sample estimate for a 3-story, "
                    "45,000 SF steel-frame office building with "
                    "curtain wall exterior in Baltimore, MD. "
                    "It demonstrates the Cantena cost estimation "
                    "pipeline without requiring a PDF upload or "
                    "API key."
                ),
                "warnings": [],
            },
            "processing_time_seconds": 0.0,
            "pages_analyzed": 0,
        }

    return app
