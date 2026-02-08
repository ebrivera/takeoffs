"""Tests for the FastAPI application — all pipeline calls are mocked."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from cantena.api.app import create_app
from cantena.exceptions import PdfProcessingError, VlmAnalysisError
from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import BuildingType, Confidence, ExteriorWall, StructuralSystem
from cantena.models.estimate import (
    BuildingSummary,
    CostEstimate,
    CostRange,
    EstimateMetadata,
)
from cantena.services.pipeline import AnalysisPipeline, PipelineResult
from cantena.services.vlm_analyzer import VlmAnalysisResult

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_building_model() -> BuildingModel:
    return BuildingModel(
        building_type=BuildingType.OFFICE_MID_RISE,
        building_use="General office",
        gross_sf=45000.0,
        stories=3,
        story_height_ft=13.0,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall_system=ExteriorWall.CURTAIN_WALL,
        location=Location(city="Baltimore", state="MD"),
        complexity_scores=ComplexityScores(),
        confidence={"building_type": Confidence.HIGH},
    )


def _make_cost_estimate() -> CostEstimate:
    return CostEstimate(
        project_name="Test Project",
        building_summary=BuildingSummary(
            building_type="office_mid_rise",
            gross_sf=45000.0,
            stories=3,
            structural_system="steel_frame",
            exterior_wall="curtain_wall",
            location="Baltimore, MD",
        ),
        total_cost=CostRange(low=8_000_000, expected=10_000_000, high=12_500_000),
        cost_per_sf=CostRange(low=178.0, expected=222.0, high=278.0),
        breakdown=[],
        assumptions=[],
        location_factor=1.02,
        metadata=EstimateMetadata(
            engine_version="0.1.0",
            cost_data_version="2025.1",
        ),
    )


def _make_vlm_result() -> VlmAnalysisResult:
    return VlmAnalysisResult(
        building_model=_make_building_model(),
        raw_response="reasoning\n```json\n{}\n```",
        reasoning="reasoning",
        warnings=[],
    )


def _make_pipeline_result() -> PipelineResult:
    return PipelineResult(
        estimate=_make_cost_estimate(),
        analysis=_make_vlm_result(),
        processing_time_seconds=2.5,
        pages_analyzed=1,
    )


def _make_mock_pipeline() -> MagicMock:
    mock = MagicMock(spec=AnalysisPipeline)
    mock.analyze.return_value = _make_pipeline_result()
    return mock


def _create_test_client(
    pipeline: AnalysisPipeline | None = None,
    cost_engine: object | None = None,
) -> TestClient:
    app = create_app(pipeline=pipeline, cost_engine=cost_engine)  # type: ignore[arg-type]
    return TestClient(app)


def _make_pdf_bytes() -> bytes:
    """Create minimal valid PDF bytes."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n"
    )


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self) -> None:
        client = _create_test_client()
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# Analyze endpoint — happy path
# ---------------------------------------------------------------------------


class TestAnalyzeSuccess:
    def test_analyze_with_pdf_returns_200(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        client = _create_test_client(pipeline=mock_pipeline)

        response = client.post(
            "/api/analyze",
            files={"file": ("plan.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            data={
                "project_name": "Test Project",
                "city": "Baltimore",
                "state": "MD",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "estimate" in data
        assert "summary_dict" in data
        assert "export_dict" in data
        assert "analysis" in data
        assert "processing_time_seconds" in data
        assert "pages_analyzed" in data

        # Verify estimate content
        assert data["estimate"]["project_name"] == "Test Project"
        assert data["processing_time_seconds"] == 2.5
        assert data["pages_analyzed"] == 1

    def test_analyze_passes_location_to_pipeline(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        client = _create_test_client(pipeline=mock_pipeline)

        client.post(
            "/api/analyze",
            files={"file": ("plan.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            data={
                "project_name": "My Project",
                "city": "New York",
                "state": "NY",
            },
        )

        call_kwargs = mock_pipeline.analyze.call_args.kwargs
        assert call_kwargs["project_name"] == "My Project"
        assert call_kwargs["location"] == "New York, NY"

    def test_response_includes_summary_dict(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        client = _create_test_client(pipeline=mock_pipeline)

        response = client.post(
            "/api/analyze",
            files={"file": ("plan.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            data={
                "project_name": "Test",
                "city": "Baltimore",
                "state": "MD",
            },
        )

        data = response.json()
        summary = data["summary_dict"]
        assert "project_name" in summary
        assert "total_cost_formatted" in summary
        assert "cost_per_sf_formatted" in summary

    def test_response_includes_export_dict(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        client = _create_test_client(pipeline=mock_pipeline)

        response = client.post(
            "/api/analyze",
            files={"file": ("plan.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            data={
                "project_name": "Test",
                "city": "Baltimore",
                "state": "MD",
            },
        )

        data = response.json()
        export = data["export_dict"]
        assert "project_name" in export
        assert "total_cost" in export
        assert "breakdown" in export


# ---------------------------------------------------------------------------
# Analyze endpoint — validation errors
# ---------------------------------------------------------------------------


class TestAnalyzeValidation:
    def test_non_pdf_returns_400(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        client = _create_test_client(pipeline=mock_pipeline)

        response = client.post(
            "/api/analyze",
            files={"file": ("image.png", io.BytesIO(b"fake png"), "image/png")},
            data={
                "project_name": "Test",
                "city": "Baltimore",
                "state": "MD",
            },
        )

        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_missing_fields_returns_422(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        client = _create_test_client(pipeline=mock_pipeline)

        # Missing city and state
        response = client.post(
            "/api/analyze",
            files={"file": ("plan.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            data={"project_name": "Test"},
        )

        assert response.status_code == 422

    def test_missing_file_returns_422(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        client = _create_test_client(pipeline=mock_pipeline)

        response = client.post(
            "/api/analyze",
            data={
                "project_name": "Test",
                "city": "Baltimore",
                "state": "MD",
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Analyze endpoint — pipeline errors
# ---------------------------------------------------------------------------


class TestAnalyzePipelineErrors:
    def test_pipeline_error_returns_500(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        mock_pipeline.analyze.side_effect = PdfProcessingError("Corrupt PDF")
        client = _create_test_client(pipeline=mock_pipeline)

        response = client.post(
            "/api/analyze",
            files={"file": ("plan.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            data={
                "project_name": "Test",
                "city": "Baltimore",
                "state": "MD",
            },
        )

        assert response.status_code == 500
        assert "Corrupt PDF" in response.json()["detail"]

    def test_vlm_error_returns_500(self) -> None:
        mock_pipeline = _make_mock_pipeline()
        mock_pipeline.analyze.side_effect = VlmAnalysisError("API timeout")
        client = _create_test_client(pipeline=mock_pipeline)

        response = client.post(
            "/api/analyze",
            files={"file": ("plan.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            data={
                "project_name": "Test",
                "city": "Baltimore",
                "state": "MD",
            },
        )

        assert response.status_code == 500
        assert "API timeout" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Estimate endpoint — direct BuildingModel → CostEstimate
# ---------------------------------------------------------------------------


class TestEstimateEndpoint:
    def test_valid_building_model_returns_200(self) -> None:
        mock_engine = MagicMock()
        mock_engine.estimate.return_value = _make_cost_estimate()
        client = _create_test_client(cost_engine=mock_engine)

        body = _make_building_model().model_dump(mode="json")
        response = client.post("/api/estimate", json=body)

        assert response.status_code == 200
        data = response.json()
        assert data["project_name"] == "Test Project"
        assert "total_cost" in data
        assert "breakdown" in data

    def test_invalid_data_returns_422(self) -> None:
        mock_engine = MagicMock()
        client = _create_test_client(cost_engine=mock_engine)

        response = client.post("/api/estimate", json={"bad": "data"})

        assert response.status_code == 422
