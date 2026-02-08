"""FastAPI application — create_app factory with /api/analyze and /api/health."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from cantena.exceptions import CantenaError

if TYPE_CHECKING:
    from cantena.services.pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)


def create_app(
    *,
    pipeline: AnalysisPipeline | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    pipeline
        Optional pre-built pipeline for dependency injection (e.g. tests).
        If not provided, one is created from environment variables on first
        request to /api/analyze.
    """
    app = FastAPI(title="Cantena", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store pipeline on app state so tests can inject mocks
    app.state.pipeline = pipeline

    def _get_pipeline() -> AnalysisPipeline:
        pl: AnalysisPipeline | None = app.state.pipeline
        if pl is not None:
            return pl
        # Lazy-create from environment
        from cantena.api.deps import create_pipeline

        pl = create_pipeline()
        app.state.pipeline = pl
        return pl

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
                "summary_dict": estimate.to_summary_dict(),
                "export_dict": estimate.to_export_dict(),
                "analysis": {
                    "reasoning": result.analysis.reasoning,
                    "warnings": result.analysis.warnings,
                },
                "processing_time_seconds": result.processing_time_seconds,
                "pages_analyzed": result.pages_analyzed,
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

    return app
