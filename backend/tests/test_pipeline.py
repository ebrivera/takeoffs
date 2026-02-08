"""Tests for the analysis pipeline — all external services are mocked."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cantena.engine import CostEngine
from cantena.exceptions import (
    CostEstimationError,
    PdfProcessingError,
    VlmAnalysisError,
)
from cantena.geometry.extractor import DrawingData
from cantena.geometry.measurement import MeasurementConfidence, PageMeasurements
from cantena.geometry.scale import ScaleResult
from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import (
    BuildingType,
    Confidence,
    ExteriorWall,
    StructuralSystem,
)
from cantena.models.estimate import (
    BuildingSummary,
    CostEstimate,
    CostRange,
    EstimateMetadata,
)
from cantena.services.hybrid_analyzer import (
    HybridAnalysisResult,
    HybridAnalyzer,
    MergeDecision,
    MergeSource,
)
from cantena.services.pdf_processor import PageResult, PdfProcessingResult, PdfProcessor
from cantena.services.pipeline import AnalysisPipeline, PipelineResult
from cantena.services.vlm_analyzer import VlmAnalysisResult, VlmAnalyzer

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


def _make_vlm_result() -> VlmAnalysisResult:
    return VlmAnalysisResult(
        building_model=_make_building_model(),
        raw_response="reasoning text\n```json\n{...}\n```",
        reasoning="reasoning text",
        warnings=[],
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


def _make_page_result(
    page_number: int = 1,
    width: int = 2000,
    height: int = 1500,
    title_block_text: str | None = None,
) -> PageResult:
    return PageResult(
        page_number=page_number,
        image_path=Path(f"/tmp/page_{page_number}.png"),
        width_px=width,
        height_px=height,
        text_content="some text",
        title_block_text=title_block_text,
    )


def _make_pdf_result(pages: list[PageResult] | None = None) -> PdfProcessingResult:
    if pages is None:
        pages = [_make_page_result()]
    return PdfProcessingResult(
        pages=pages,
        page_count=len(pages),
        file_size_bytes=1024,
    )


def _make_pipeline() -> tuple[AnalysisPipeline, MagicMock, MagicMock, MagicMock]:
    """Create a pipeline with mocked dependencies."""
    mock_pdf = MagicMock(spec=PdfProcessor)
    mock_vlm = MagicMock(spec=VlmAnalyzer)
    mock_engine = MagicMock(spec=CostEngine)

    pipeline = AnalysisPipeline(
        pdf_processor=mock_pdf,
        vlm_analyzer=mock_vlm,
        cost_engine=mock_engine,
    )
    return pipeline, mock_pdf, mock_vlm, mock_engine


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_full_pipeline_returns_result(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        pdf_result = _make_pdf_result()
        vlm_result = _make_vlm_result()
        estimate = _make_cost_estimate()

        mock_pdf.process.return_value = pdf_result
        mock_vlm.analyze.return_value = vlm_result
        mock_engine.estimate.return_value = estimate

        result = pipeline.analyze(
            pdf_path=Path("/tmp/test.pdf"),
            project_name="Test Project",
            location="Baltimore, MD",
        )

        assert isinstance(result, PipelineResult)
        assert result.estimate is estimate
        assert result.analysis is vlm_result
        assert result.pages_analyzed == 1
        assert result.processing_time_seconds >= 0

    def test_cleanup_called_on_success(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        pdf_result = _make_pdf_result()
        mock_pdf.process.return_value = pdf_result
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        pipeline.analyze(
            pdf_path=Path("/tmp/test.pdf"),
            project_name="Test",
            location="Baltimore, MD",
        )

        mock_pdf.cleanup.assert_called_once_with(pdf_result)

    def test_vlm_receives_context(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        pipeline.analyze(
            pdf_path=Path("/tmp/test.pdf"),
            project_name="My Project",
            location="New York, NY",
        )

        call_kwargs = mock_vlm.analyze.call_args
        ctx = call_kwargs.kwargs.get("context") or call_kwargs[1].get("context")
        assert ctx.project_name == "My Project"
        assert ctx.location == "New York, NY"


# ---------------------------------------------------------------------------
# Page selection
# ---------------------------------------------------------------------------


class TestPageSelection:
    def test_selects_page_with_floor_plan_in_title(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        pages = [
            _make_page_result(1, title_block_text="COVER SHEET"),
            _make_page_result(2, title_block_text="A101 - FIRST FLOOR PLAN"),
            _make_page_result(3, title_block_text="ELEVATIONS"),
        ]
        mock_pdf.process.return_value = _make_pdf_result(pages)
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        # VLM should get page 2's image
        call_kwargs = mock_vlm.analyze.call_args
        image_path = call_kwargs.kwargs.get("image_path") or call_kwargs[0][0]
        assert "page_2" in str(image_path)

    def test_selects_largest_page_when_no_floor_plan_title(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        pages = [
            _make_page_result(1, width=1000, height=1000),
            _make_page_result(2, width=3000, height=2000),  # largest
            _make_page_result(3, width=1500, height=1500),
        ]
        mock_pdf.process.return_value = _make_pdf_result(pages)
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        call_kwargs = mock_vlm.analyze.call_args
        image_path = call_kwargs.kwargs.get("image_path") or call_kwargs[0][0]
        assert "page_2" in str(image_path)


# ---------------------------------------------------------------------------
# Error wrapping
# ---------------------------------------------------------------------------


class TestPdfErrorWrapping:
    def test_pdf_processing_error_wrapped(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.side_effect = ValueError("Bad PDF")

        with pytest.raises(PdfProcessingError, match="Failed to process PDF"):
            pipeline.analyze(Path("/tmp/bad.pdf"), "Test", "Baltimore, MD")

    def test_empty_pdf_raises_error(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.return_value = PdfProcessingResult(
            pages=[], page_count=0, file_size_bytes=100,
        )

        with pytest.raises(PdfProcessingError, match="no pages"):
            pipeline.analyze(Path("/tmp/empty.pdf"), "Test", "Baltimore, MD")


class TestVlmErrorWrapping:
    def test_vlm_error_wrapped(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.side_effect = ValueError("API failure")

        with pytest.raises(VlmAnalysisError, match="VLM analysis failed"):
            pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

    def test_vlm_analysis_error_not_double_wrapped(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.return_value = _make_pdf_result()
        original = VlmAnalysisError("original error")
        mock_vlm.analyze.side_effect = original

        with pytest.raises(VlmAnalysisError, match="original error"):
            pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")


class TestCostEngineErrorWrapping:
    def test_cost_engine_error_wrapped(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.side_effect = ValueError("No cost data")

        with pytest.raises(CostEstimationError, match="Cost estimation failed"):
            pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

    def test_cost_estimation_error_not_double_wrapped(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.return_value = _make_vlm_result()
        original = CostEstimationError("original error")
        mock_engine.estimate.side_effect = original

        with pytest.raises(CostEstimationError, match="original error"):
            pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")


# ---------------------------------------------------------------------------
# Cleanup on failure
# ---------------------------------------------------------------------------


class TestCleanupOnFailure:
    def test_cleanup_called_on_vlm_error(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        pdf_result = _make_pdf_result()
        mock_pdf.process.return_value = pdf_result
        mock_vlm.analyze.side_effect = ValueError("VLM fail")

        with pytest.raises(VlmAnalysisError):
            pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        mock_pdf.cleanup.assert_called_once_with(pdf_result)

    def test_cleanup_called_on_cost_engine_error(self) -> None:
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        pdf_result = _make_pdf_result()
        mock_pdf.process.return_value = pdf_result
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.side_effect = ValueError("Engine fail")

        with pytest.raises(CostEstimationError):
            pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        mock_pdf.cleanup.assert_called_once_with(pdf_result)

    def test_no_cleanup_on_pdf_process_error(self) -> None:
        """If PDF processing fails, there's nothing to clean up."""
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.side_effect = ValueError("Bad PDF")

        with pytest.raises(PdfProcessingError):
            pipeline.analyze(Path("/tmp/bad.pdf"), "Test", "Baltimore, MD")

        mock_pdf.cleanup.assert_not_called()


# ---------------------------------------------------------------------------
# Hybrid analysis integration
# ---------------------------------------------------------------------------


def _make_hybrid_result() -> HybridAnalysisResult:
    """Create a HybridAnalysisResult with sensible defaults."""
    model = _make_building_model()
    vlm_result = _make_vlm_result()
    scale = ScaleResult(
        drawing_units=0.125,
        real_units=12.0,
        scale_factor=96.0,
        notation='1/8"=1\'-0"',
        confidence=Confidence.HIGH,
    )
    measurements = PageMeasurements(
        scale=scale,
        gross_area_sf=45000.0,
        building_perimeter_lf=850.0,
        total_wall_length_lf=2400.0,
        wall_count=12,
        confidence=MeasurementConfidence.HIGH,
        raw_data=DrawingData(
            paths=[],
            page_width_pts=612.0,
            page_height_pts=792.0,
            page_size_inches=(8.5, 11.0),
        ),
    )
    return HybridAnalysisResult(
        building_model=model,
        geometry_measurements=measurements,
        vlm_result=vlm_result,
        merge_decisions=[
            MergeDecision(
                field_name="gross_sf",
                source=MergeSource.GEOMETRY,
                value="45000.0",
                reasoning="Geometry computed 45000 SF",
                confidence=Confidence.HIGH,
            ),
        ],
    )


def _make_hybrid_pipeline() -> (
    tuple[AnalysisPipeline, MagicMock, MagicMock, MagicMock, MagicMock]
):
    """Create pipeline with HybridAnalyzer mock."""
    mock_pdf = MagicMock(spec=PdfProcessor)
    mock_vlm = MagicMock(spec=VlmAnalyzer)
    mock_engine = MagicMock(spec=CostEngine)
    mock_hybrid = MagicMock(spec=HybridAnalyzer)

    pipeline = AnalysisPipeline(
        pdf_processor=mock_pdf,
        vlm_analyzer=mock_vlm,
        cost_engine=mock_engine,
        hybrid_analyzer=mock_hybrid,
    )
    return pipeline, mock_pdf, mock_vlm, mock_engine, mock_hybrid


class TestHybridAnalysis:
    """Vector-rich PDF uses HybridAnalyzer."""

    @patch.object(
        AnalysisPipeline,
        "_count_vector_paths",
        return_value=100,
    )
    @patch.object(
        AnalysisPipeline,
        "_run_hybrid_analysis",
    )
    def test_vector_rich_pdf_uses_hybrid(
        self,
        mock_run_hybrid: MagicMock,
        _mock_count: MagicMock,
    ) -> None:
        """Pipeline uses HybridAnalyzer when >50 paths found."""
        pipeline, mock_pdf, mock_vlm, mock_engine, mock_hybrid = (
            _make_hybrid_pipeline()
        )

        mock_pdf.process.return_value = _make_pdf_result()
        hybrid_result = _make_hybrid_result()
        mock_run_hybrid.return_value = hybrid_result
        mock_engine.estimate.return_value = _make_cost_estimate()

        result = pipeline.analyze(
            Path("/tmp/test.pdf"), "Test", "Baltimore, MD"
        )

        assert result.geometry_available is True
        assert (
            result.measurement_confidence
            == MeasurementConfidence.HIGH
        )
        assert result.merge_decisions is not None
        assert len(result.merge_decisions) == 1
        # VLM analyze should NOT be called directly
        mock_vlm.analyze.assert_not_called()

    @patch.object(
        AnalysisPipeline,
        "_count_vector_paths",
        return_value=10,
    )
    def test_scanned_pdf_falls_back_to_vlm(
        self,
        _mock_count: MagicMock,
    ) -> None:
        """Pipeline falls back to VLM-only when <=50 paths."""
        pipeline, mock_pdf, mock_vlm, mock_engine, mock_hybrid = (
            _make_hybrid_pipeline()
        )

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        result = pipeline.analyze(
            Path("/tmp/test.pdf"), "Test", "Baltimore, MD"
        )

        assert result.geometry_available is False
        assert (
            result.measurement_confidence
            == MeasurementConfidence.NONE
        )
        assert result.merge_decisions is None
        mock_vlm.analyze.assert_called_once()
        mock_hybrid.analyze.assert_not_called()


class TestPipelineResultGeometryFields:
    """PipelineResult includes geometry fields."""

    def test_vlm_only_result_has_geometry_defaults(self) -> None:
        """Without hybrid, geometry fields have default values."""
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        result = pipeline.analyze(
            Path("/tmp/test.pdf"), "Test", "Baltimore, MD"
        )

        assert result.geometry_available is False
        assert (
            result.measurement_confidence
            == MeasurementConfidence.NONE
        )
        assert result.merge_decisions is None

    @patch.object(
        AnalysisPipeline,
        "_count_vector_paths",
        return_value=200,
    )
    @patch.object(
        AnalysisPipeline,
        "_run_hybrid_analysis",
    )
    def test_hybrid_result_populates_geometry_fields(
        self,
        mock_run_hybrid: MagicMock,
        _mock_count: MagicMock,
    ) -> None:
        """Hybrid analysis populates all geometry fields."""
        pipeline, mock_pdf, mock_vlm, mock_engine, mock_hybrid = (
            _make_hybrid_pipeline()
        )

        mock_pdf.process.return_value = _make_pdf_result()
        hybrid_result = _make_hybrid_result()
        mock_run_hybrid.return_value = hybrid_result
        mock_engine.estimate.return_value = _make_cost_estimate()

        result = pipeline.analyze(
            Path("/tmp/test.pdf"), "Test", "Baltimore, MD"
        )

        assert result.geometry_available is True
        assert result.measurement_confidence == (
            MeasurementConfidence.HIGH
        )
        assert result.merge_decisions is not None


class TestBackwardCompatible:
    """Backward compatible without HybridAnalyzer configured."""

    def test_no_hybrid_analyzer_uses_vlm_only(self) -> None:
        """Pipeline without hybrid_analyzer param works as before."""
        pipeline, mock_pdf, mock_vlm, mock_engine = _make_pipeline()

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        result = pipeline.analyze(
            Path("/tmp/test.pdf"), "Test", "Baltimore, MD"
        )

        assert isinstance(result, PipelineResult)
        assert result.geometry_available is False
        mock_vlm.analyze.assert_called_once()
