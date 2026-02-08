"""Tests for cantena.services.hybrid_analyzer — hybrid geometry + VLM analysis."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from cantena.geometry.extractor import DrawingData
from cantena.geometry.measurement import (
    MeasurementConfidence,
    MeasurementService,
    PageMeasurements,
)
from cantena.geometry.scale import Confidence, ScaleResult
from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import (
    BuildingType,
    ExteriorWall,
    StructuralSystem,
)
from cantena.services.hybrid_analyzer import (
    HybridAnalyzer,
    MergeSource,
)
from cantena.services.vlm_analyzer import VlmAnalysisResult, VlmAnalyzer


def _make_vlm_result(
    gross_sf: float = 42000.0,
    building_type: BuildingType = BuildingType.OFFICE_MID_RISE,
    confidence_gross_sf: Confidence = Confidence.MEDIUM,
) -> VlmAnalysisResult:
    """Create a VlmAnalysisResult with sensible defaults."""
    model = BuildingModel(
        building_type=building_type,
        building_use="General office",
        gross_sf=gross_sf,
        stories=3,
        story_height_ft=12.0,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall_system=ExteriorWall.CURTAIN_WALL,
        location=Location(city="Baltimore", state="MD"),
        complexity_scores=ComplexityScores(),
        special_conditions=[],
        confidence={
            "building_type": Confidence.HIGH,
            "gross_sf": confidence_gross_sf,
            "stories": Confidence.HIGH,
            "structural_system": Confidence.MEDIUM,
            "exterior_wall_system": Confidence.MEDIUM,
        },
    )
    return VlmAnalysisResult(
        building_model=model,
        raw_response="test response",
        reasoning="test reasoning",
        warnings=[],
    )


def _make_empty_drawing_data() -> DrawingData:
    """Empty DrawingData for measurements with no geometry."""
    return DrawingData(
        paths=[],
        page_width_pts=612.0,
        page_height_pts=792.0,
        page_size_inches=(8.5, 11.0),
    )


def _make_measurements(
    gross_area_sf: float | None = 45000.0,
    confidence: MeasurementConfidence = MeasurementConfidence.HIGH,
    wall_count: int = 12,
) -> PageMeasurements:
    """Create PageMeasurements with specified values."""
    scale = ScaleResult(
        drawing_units=0.125,
        real_units=12.0,
        scale_factor=96.0,
        notation='1/8"=1\'-0"',
        confidence=Confidence.HIGH,
    )
    return PageMeasurements(
        scale=scale if confidence != MeasurementConfidence.NONE else None,
        gross_area_sf=gross_area_sf,
        building_perimeter_lf=850.0 if gross_area_sf else None,
        total_wall_length_lf=2400.0 if gross_area_sf else None,
        wall_count=wall_count,
        confidence=confidence,
        raw_data=_make_empty_drawing_data(),
    )


class TestGeometryHighConfidence:
    """Geometry HIGH 45000 SF + VLM 42000 SF -> merged uses geometry."""

    def test_uses_geometry_area(self) -> None:
        """When geometry is HIGH confidence, merged model uses geometry SF."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements(
            gross_area_sf=45000.0,
            confidence=MeasurementConfidence.HIGH,
        )

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result(
            gross_sf=42000.0
        )

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert result.building_model.gross_sf == 45000.0
        # Check merge decision documents this
        sf_decision = next(
            d for d in result.merge_decisions
            if d.field_name == "gross_sf"
        )
        assert sf_decision.source == MergeSource.GEOMETRY
        assert sf_decision.confidence == Confidence.HIGH

    def test_medium_confidence_also_uses_geometry(self) -> None:
        """MEDIUM confidence geometry is still preferred over VLM."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements(
            gross_area_sf=45000.0,
            confidence=MeasurementConfidence.MEDIUM,
        )

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result(
            gross_sf=42000.0
        )

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert result.building_model.gross_sf == 45000.0


class TestGeometryNoneFallsBackToVLM:
    """Geometry NONE -> falls back to VLM."""

    def test_none_confidence_uses_vlm(self) -> None:
        """When geometry has NONE confidence, use VLM gross_sf."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements(
            gross_area_sf=None,
            confidence=MeasurementConfidence.NONE,
            wall_count=0,
        )

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result(
            gross_sf=42000.0,
        )

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert result.building_model.gross_sf == 42000.0
        sf_decision = next(
            d for d in result.merge_decisions
            if d.field_name == "gross_sf"
        )
        assert sf_decision.source == MergeSource.VLM

    def test_low_confidence_uses_vlm(self) -> None:
        """When geometry has LOW confidence, use VLM gross_sf."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements(
            gross_area_sf=50000.0,
            confidence=MeasurementConfidence.LOW,
        )

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result(
            gross_sf=42000.0,
        )

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert result.building_model.gross_sf == 42000.0


class TestBuildingTypeAlwaysFromVLM:
    """Building type always from VLM."""

    def test_building_type_from_vlm(self) -> None:
        """building_type always sourced from VLM, not geometry."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements()

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result(
            building_type=BuildingType.WAREHOUSE,
        )

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert (
            result.building_model.building_type
            == BuildingType.WAREHOUSE
        )
        bt_decision = next(
            d for d in result.merge_decisions
            if d.field_name == "building_type"
        )
        assert bt_decision.source == MergeSource.VLM

    def test_stories_from_vlm(self) -> None:
        """stories always sourced from VLM."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements()

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result()

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert result.building_model.stories == 3
        stories_decision = next(
            d for d in result.merge_decisions
            if d.field_name == "stories"
        )
        assert stories_decision.source == MergeSource.VLM


class TestMergeDecisionsDocumented:
    """Verify merge decisions are fully documented."""

    def test_all_key_fields_have_decisions(self) -> None:
        """Every key merged field has a MergeDecision entry."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements()

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result()

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        decision_fields = {d.field_name for d in result.merge_decisions}
        assert "gross_sf" in decision_fields
        assert "building_type" in decision_fields
        assert "stories" in decision_fields
        assert "structural_system" in decision_fields
        assert "exterior_wall_system" in decision_fields
        assert "story_height_ft" in decision_fields

    def test_decisions_have_reasoning(self) -> None:
        """Every MergeDecision has non-empty reasoning."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements()

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result()

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        for decision in result.merge_decisions:
            assert decision.reasoning, (
                f"Missing reasoning for {decision.field_name}"
            )


class TestGeometryAnomalies:
    """Geometry anomalies added to special_conditions."""

    def test_large_discrepancy_noted(self) -> None:
        """Large geometry/VLM area discrepancy added to special_conditions."""
        mock_ms = MagicMock(spec=MeasurementService)
        # Geometry says 45000, VLM says 30000 -> >20% discrepancy
        mock_ms.measure.return_value = _make_measurements(
            gross_area_sf=45000.0,
            confidence=MeasurementConfidence.HIGH,
        )

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result(
            gross_sf=30000.0,
        )

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert any(
            "discrepancy" in cond.lower()
            for cond in result.building_model.special_conditions
        )

    def test_small_discrepancy_not_noted(self) -> None:
        """Small discrepancy (<20%) does NOT add special_condition."""
        mock_ms = MagicMock(spec=MeasurementService)
        # Geometry says 45000, VLM says 42000 -> ~7% discrepancy
        mock_ms.measure.return_value = _make_measurements(
            gross_area_sf=45000.0,
            confidence=MeasurementConfidence.HIGH,
        )

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result(
            gross_sf=42000.0,
        )

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert not any(
            "discrepancy" in cond.lower()
            for cond in result.building_model.special_conditions
        )

    def test_low_confidence_geometry_noted(self) -> None:
        """LOW confidence geometry adds estimation note to conditions."""
        mock_ms = MagicMock(spec=MeasurementService)
        mock_ms.measure.return_value = _make_measurements(
            gross_area_sf=50000.0,
            confidence=MeasurementConfidence.LOW,
        )

        mock_vlm = MagicMock(spec=VlmAnalyzer)
        mock_vlm.analyze.return_value = _make_vlm_result(
            gross_sf=42000.0,
        )

        analyzer = HybridAnalyzer(
            measurement_service=mock_ms,
            vlm_analyzer=mock_vlm,
        )

        mock_page = MagicMock()
        result = analyzer.analyze(
            page=mock_page,
            image_path=Path("/fake/image.png"),
        )

        assert any(
            "low confidence" in cond.lower()
            for cond in result.building_model.special_conditions
        )
