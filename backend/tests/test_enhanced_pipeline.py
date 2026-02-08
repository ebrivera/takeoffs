"""Tests for the enhanced pipeline: geometry rooms + LLM enrichment + room-type costing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cantena.engine import CostEngine
from cantena.geometry.extractor import DrawingData
from cantena.geometry.measurement import MeasurementConfidence, PageMeasurements
from cantena.geometry.scale import ScaleResult
from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import (
    BuildingType,
    Confidence,
    ExteriorWall,
    RoomType,
    StructuralSystem,
)
from cantena.models.estimate import (
    BuildingSummary,
    CostEstimate,
    CostRange,
    EstimateMetadata,
    SpaceCost,
)
from cantena.models.space_program import Space, SpaceProgram, SpaceSource
from cantena.services.hybrid_analyzer import (
    HybridAnalysisResult,
    HybridAnalyzer,
    MergeDecision,
    MergeSource,
)
from cantena.services.pdf_processor import PageResult, PdfProcessingResult, PdfProcessor
from cantena.services.pipeline import AnalysisPipeline, PipelineResult
from cantena.services.space_assembler import SpaceAssembler
from cantena.services.vlm_analyzer import VlmAnalysisResult, VlmAnalyzer

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_building_model(
    building_type: BuildingType = BuildingType.APARTMENT_LOW_RISE,
    gross_sf: float = 1000.0,
) -> BuildingModel:
    return BuildingModel(
        building_type=building_type,
        building_use="Residential",
        gross_sf=gross_sf,
        stories=1,
        story_height_ft=10.0,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall_system=ExteriorWall.WOOD_SIDING,
        location=Location(city="Baltimore", state="MD"),
        complexity_scores=ComplexityScores(),
        confidence={"building_type": Confidence.HIGH},
    )


def _make_vlm_result(
    building_type: BuildingType = BuildingType.APARTMENT_LOW_RISE,
    gross_sf: float = 1000.0,
) -> VlmAnalysisResult:
    return VlmAnalysisResult(
        building_model=_make_building_model(building_type, gross_sf),
        raw_response="reasoning\n```json\n{}\n```",
        reasoning="reasoning",
        warnings=[],
    )


def _make_space_breakdown() -> list[SpaceCost]:
    return [
        SpaceCost(
            room_type="kitchen",
            name="Kitchen",
            area_sf=120.0,
            cost_per_sf=CostRange(low=200.0, expected=250.0, high=312.5),
            total_cost=CostRange(low=24000.0, expected=30000.0, high=37500.0),
            percent_of_total=40.0,
            source="geometry",
        ),
        SpaceCost(
            room_type="living_room",
            name="Living Room",
            area_sf=200.0,
            cost_per_sf=CostRange(low=144.0, expected=180.0, high=225.0),
            total_cost=CostRange(low=28800.0, expected=36000.0, high=45000.0),
            percent_of_total=50.0,
            source="geometry",
        ),
        SpaceCost(
            room_type="utility",
            name="Utility",
            area_sf=50.0,
            cost_per_sf=CostRange(low=80.0, expected=100.0, high=125.0),
            total_cost=CostRange(low=4000.0, expected=5000.0, high=6250.0),
            percent_of_total=10.0,
            source="geometry",
        ),
    ]


def _make_cost_estimate(
    space_breakdown: list[SpaceCost] | None = None,
) -> CostEstimate:
    total_expected = 71000.0 if space_breakdown else 200000.0
    return CostEstimate(
        project_name="Test Project",
        building_summary=BuildingSummary(
            building_type="apartment_low_rise",
            gross_sf=1000.0,
            stories=1,
            structural_system="wood_frame",
            exterior_wall="wood_siding",
            location="Baltimore, MD",
        ),
        total_cost=CostRange(
            low=total_expected * 0.80,
            expected=total_expected,
            high=total_expected * 1.25,
        ),
        cost_per_sf=CostRange(
            low=total_expected * 0.80 / 1000.0,
            expected=total_expected / 1000.0,
            high=total_expected * 1.25 / 1000.0,
        ),
        breakdown=[],
        assumptions=[],
        location_factor=1.02,
        metadata=EstimateMetadata(
            engine_version="0.1.0",
            cost_data_version="2025.1",
        ),
        space_breakdown=space_breakdown,
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


def _make_pdf_result() -> PdfProcessingResult:
    return PdfProcessingResult(
        pages=[_make_page_result()],
        page_count=1,
        file_size_bytes=1024,
    )


@dataclass(frozen=True)
class _StubDetectedRoom:
    label: str | None
    area_sf: float | None
    room_index: int
    polygon_pts: list[tuple[float, float]] = field(default_factory=list)
    area_pts: float = 0.0
    perimeter_pts: float = 0.0
    perimeter_lf: float | None = None
    centroid: Any = None


def _make_geometry_measurements(
    rooms: list[_StubDetectedRoom] | None = None,
    gross_area_sf: float = 1000.0,
) -> PageMeasurements:
    scale = ScaleResult(
        drawing_units=0.25,
        real_units=12.0,
        scale_factor=48.0,
        notation='1/4"=1\'-0"',
        confidence=Confidence.HIGH,
    )
    return PageMeasurements(
        scale=scale,
        gross_area_sf=gross_area_sf,
        building_perimeter_lf=130.0,
        total_wall_length_lf=300.0,
        wall_count=10,
        confidence=MeasurementConfidence.HIGH,
        raw_data=DrawingData(
            paths=[],
            page_width_pts=612.0,
            page_height_pts=792.0,
            page_size_inches=(8.5, 11.0),
        ),
        rooms=rooms,  # type: ignore[arg-type]
        room_count=len(rooms) if rooms else 0,
        polygonize_success=bool(rooms),
    )


def _make_hybrid_result(
    rooms: list[_StubDetectedRoom] | None = None,
    gross_area_sf: float = 1000.0,
) -> HybridAnalysisResult:
    model = _make_building_model(gross_sf=gross_area_sf)
    vlm_result = _make_vlm_result(gross_sf=gross_area_sf)
    measurements = _make_geometry_measurements(rooms, gross_area_sf)
    return HybridAnalysisResult(
        building_model=model,
        geometry_measurements=measurements,
        vlm_result=vlm_result,
        merge_decisions=[
            MergeDecision(
                field_name="gross_sf",
                source=MergeSource.GEOMETRY,
                value=str(gross_area_sf),
                reasoning="Geometry computed area",
                confidence=Confidence.HIGH,
            ),
        ],
    )


def _make_enhanced_pipeline(
    with_assembler: bool = True,
) -> tuple[
    AnalysisPipeline,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    SpaceAssembler | None,
]:
    mock_pdf = MagicMock(spec=PdfProcessor)
    mock_vlm = MagicMock(spec=VlmAnalyzer)
    mock_engine = MagicMock(spec=CostEngine)
    mock_hybrid = MagicMock(spec=HybridAnalyzer)
    assembler = SpaceAssembler() if with_assembler else None

    pipeline = AnalysisPipeline(
        pdf_processor=mock_pdf,
        vlm_analyzer=mock_vlm,
        cost_engine=mock_engine,
        hybrid_analyzer=mock_hybrid,
        space_assembler=assembler,
    )
    return pipeline, mock_pdf, mock_vlm, mock_engine, mock_hybrid, assembler


# ---------------------------------------------------------------------------
# Tests: Enhanced flow with mocks returns SpaceProgram
# ---------------------------------------------------------------------------


class TestEnhancedFlowWithGeometry:
    """Enhanced pipeline with geometry rooms returns SpaceProgram + room_detection_method."""

    @patch.object(AnalysisPipeline, "_count_vector_paths", return_value=100)
    @patch.object(AnalysisPipeline, "_run_hybrid_analysis")
    def test_enhanced_flow_returns_space_program(
        self,
        mock_run_hybrid: MagicMock,
        _mock_count: MagicMock,
    ) -> None:
        pipeline, mock_pdf, _, mock_engine, _, _ = _make_enhanced_pipeline()

        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
            _StubDetectedRoom(label="LIVING ROOM", area_sf=200.0, room_index=1),
            _StubDetectedRoom(label="UTILITY", area_sf=50.0, room_index=2),
        ]
        hybrid_result = _make_hybrid_result(rooms, gross_area_sf=1000.0)
        mock_run_hybrid.return_value = hybrid_result
        mock_pdf.process.return_value = _make_pdf_result()

        space_breakdown = _make_space_breakdown()
        mock_engine.estimate.return_value = _make_cost_estimate(space_breakdown)

        result = pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        assert result.space_program is not None
        assert len(result.space_program.spaces) >= 3
        assert result.room_detection_method == "polygonize"

    @patch.object(AnalysisPipeline, "_count_vector_paths", return_value=100)
    @patch.object(AnalysisPipeline, "_run_hybrid_analysis")
    def test_space_costs_sum_to_total(
        self,
        mock_run_hybrid: MagicMock,
        _mock_count: MagicMock,
    ) -> None:
        pipeline, mock_pdf, _, mock_engine, _, _ = _make_enhanced_pipeline()

        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
            _StubDetectedRoom(label="LIVING ROOM", area_sf=200.0, room_index=1),
        ]
        hybrid_result = _make_hybrid_result(rooms, gross_area_sf=320.0)
        mock_run_hybrid.return_value = hybrid_result
        mock_pdf.process.return_value = _make_pdf_result()

        space_breakdown = [
            SpaceCost(
                room_type="kitchen",
                name="Kitchen",
                area_sf=120.0,
                cost_per_sf=CostRange(low=200.0, expected=250.0, high=312.5),
                total_cost=CostRange(low=24000.0, expected=30000.0, high=37500.0),
                percent_of_total=50.0,
                source="geometry",
            ),
            SpaceCost(
                room_type="living_room",
                name="Living Room",
                area_sf=200.0,
                cost_per_sf=CostRange(low=144.0, expected=180.0, high=225.0),
                total_cost=CostRange(low=28800.0, expected=36000.0, high=45000.0),
                percent_of_total=50.0,
                source="geometry",
            ),
        ]
        total_expected = 66000.0
        estimate = CostEstimate(
            project_name="Test",
            building_summary=BuildingSummary(
                building_type="apartment_low_rise",
                gross_sf=320.0,
                stories=1,
                structural_system="wood_frame",
                exterior_wall="wood_siding",
                location="Baltimore, MD",
            ),
            total_cost=CostRange(
                low=total_expected * 0.80,
                expected=total_expected,
                high=total_expected * 1.25,
            ),
            cost_per_sf=CostRange(
                low=total_expected * 0.80 / 320.0,
                expected=total_expected / 320.0,
                high=total_expected * 1.25 / 320.0,
            ),
            breakdown=[],
            assumptions=[],
            location_factor=1.02,
            metadata=EstimateMetadata(
                engine_version="0.1.0",
                cost_data_version="2025.1",
            ),
            space_breakdown=space_breakdown,
        )
        mock_engine.estimate.return_value = estimate

        result = pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        assert result.space_breakdown is not None
        breakdown_total = sum(sc.total_cost.expected for sc in result.space_breakdown)
        assert breakdown_total == pytest.approx(
            result.estimate.total_cost.expected, rel=0.01
        )

    @patch.object(AnalysisPipeline, "_count_vector_paths", return_value=100)
    @patch.object(AnalysisPipeline, "_run_hybrid_analysis")
    def test_engine_called_with_space_program(
        self,
        mock_run_hybrid: MagicMock,
        _mock_count: MagicMock,
    ) -> None:
        """CostEngine.estimate receives the assembled SpaceProgram."""
        pipeline, mock_pdf, _, mock_engine, _, _ = _make_enhanced_pipeline()

        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
        ]
        hybrid_result = _make_hybrid_result(rooms, gross_area_sf=500.0)
        mock_run_hybrid.return_value = hybrid_result
        mock_pdf.process.return_value = _make_pdf_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        call_kwargs = mock_engine.estimate.call_args.kwargs
        assert "space_program" in call_kwargs
        assert isinstance(call_kwargs["space_program"], SpaceProgram)


# ---------------------------------------------------------------------------
# Tests: Fallback without geometry
# ---------------------------------------------------------------------------


class TestFallbackWithoutGeometry:
    """Without geometry, pipeline falls back gracefully."""

    @patch.object(AnalysisPipeline, "_count_vector_paths", return_value=10)
    def test_no_geometry_returns_assumed_method(
        self,
        _mock_count: MagicMock,
    ) -> None:
        """VLM-only pipeline returns room_detection_method='assumed'."""
        pipeline, mock_pdf, mock_vlm, mock_engine, _, _ = (
            _make_enhanced_pipeline()
        )

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        result = pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        assert result.room_detection_method == "assumed"
        assert result.space_program is None
        assert result.space_breakdown is None


# ---------------------------------------------------------------------------
# Tests: API response includes space_breakdown
# ---------------------------------------------------------------------------


class TestApiResponseSpaceBreakdown:
    """API response includes space_breakdown when available."""

    def test_api_response_includes_space_breakdown(self) -> None:
        from cantena.api.app import create_app

        space_breakdown = _make_space_breakdown()
        estimate = _make_cost_estimate(space_breakdown)
        space_program = SpaceProgram(
            spaces=[
                Space(
                    room_type=RoomType.KITCHEN,
                    name="Kitchen",
                    area_sf=120.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
            building_type=BuildingType.APARTMENT_LOW_RISE,
        )
        vlm_result = _make_vlm_result()

        mock_pipeline = MagicMock(spec=AnalysisPipeline)
        mock_pipeline.analyze.return_value = PipelineResult(
            estimate=estimate,
            analysis=vlm_result,
            processing_time_seconds=1.0,
            pages_analyzed=1,
            geometry_available=True,
            measurement_confidence=MeasurementConfidence.HIGH,
            space_program=space_program,
            space_breakdown=space_breakdown,
            room_detection_method="polygonize",
        )

        mock_engine = MagicMock(spec=CostEngine)
        app = create_app(pipeline=mock_pipeline, cost_engine=mock_engine)

        from fastapi.testclient import TestClient

        client = TestClient(app)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            response = client.post(
                "/api/analyze",
                data={
                    "project_name": "Test",
                    "city": "Baltimore",
                    "state": "MD",
                },
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "space_breakdown" in data
        assert len(data["space_breakdown"]) == 3
        assert data["room_detection_method"] == "polygonize"
        assert data["space_breakdown"][0]["room_type"] == "kitchen"


# ---------------------------------------------------------------------------
# Tests: Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatiblePipeline:
    """Pipeline without SpaceAssembler still works as before."""

    def test_no_assembler_no_space_program(self) -> None:
        """Pipeline without space_assembler param works as before."""
        mock_pdf = MagicMock(spec=PdfProcessor)
        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_engine = MagicMock(spec=CostEngine)

        pipeline = AnalysisPipeline(
            pdf_processor=mock_pdf,
            vlm_analyzer=mock_vlm,
            cost_engine=mock_engine,
        )

        mock_pdf.process.return_value = _make_pdf_result()
        mock_vlm.analyze.return_value = _make_vlm_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        result = pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        assert isinstance(result, PipelineResult)
        assert result.space_program is None
        assert result.space_breakdown is None
        # engine called without space_program
        call_kwargs = mock_engine.estimate.call_args.kwargs
        assert call_kwargs.get("space_program") is None

    @patch.object(AnalysisPipeline, "_count_vector_paths", return_value=100)
    @patch.object(AnalysisPipeline, "_run_hybrid_analysis")
    def test_hybrid_without_assembler_no_space_program(
        self,
        mock_run_hybrid: MagicMock,
        _mock_count: MagicMock,
    ) -> None:
        """Hybrid analysis without assembler: geometry available but no SpaceProgram."""
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

        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
        ]
        mock_run_hybrid.return_value = _make_hybrid_result(rooms)
        mock_pdf.process.return_value = _make_pdf_result()
        mock_engine.estimate.return_value = _make_cost_estimate()

        result = pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        assert result.geometry_available is True
        assert result.space_program is None
        # engine called without space_program
        call_kwargs = mock_engine.estimate.call_args.kwargs
        assert call_kwargs.get("space_program") is None


# ---------------------------------------------------------------------------
# Tests: SpaceCost source tracking
# ---------------------------------------------------------------------------


class TestSpaceCostSourceTracking:
    """SpaceCost.source is populated correctly from Space.source."""

    @patch.object(AnalysisPipeline, "_count_vector_paths", return_value=100)
    @patch.object(AnalysisPipeline, "_run_hybrid_analysis")
    def test_geometry_rooms_have_geometry_source(
        self,
        mock_run_hybrid: MagicMock,
        _mock_count: MagicMock,
    ) -> None:
        pipeline, mock_pdf, _, mock_engine, _, _ = _make_enhanced_pipeline()

        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
        ]
        hybrid_result = _make_hybrid_result(rooms, gross_area_sf=500.0)
        mock_run_hybrid.return_value = hybrid_result
        mock_pdf.process.return_value = _make_pdf_result()

        # The engine is mocked, so we verify the space_program passed to it
        mock_engine.estimate.return_value = _make_cost_estimate()

        pipeline.analyze(Path("/tmp/test.pdf"), "Test", "Baltimore, MD")

        call_kwargs = mock_engine.estimate.call_args.kwargs
        program = call_kwargs["space_program"]
        # At least the first space (from geometry) has GEOMETRY source
        geometry_spaces = [
            s for s in program.spaces if s.source == SpaceSource.GEOMETRY
        ]
        assert len(geometry_spaces) >= 1
