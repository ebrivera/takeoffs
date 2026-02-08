"""Hybrid analysis: merge geometry measurements with VLM semantic analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import fitz  # type: ignore[import-untyped]

    from cantena.geometry.measurement import (
        MeasurementService,
        PageMeasurements,
    )
    from cantena.models.building import BuildingModel
    from cantena.services.vlm_analyzer import (
        AnalysisContext,
        VlmAnalysisResult,
        VlmAnalyzer,
    )

from cantena.geometry.measurement import MeasurementConfidence
from cantena.models.enums import Confidence


class MergeSource(StrEnum):
    """Source of a merged field value."""

    GEOMETRY = "geometry"
    VLM = "vlm"
    USER_OVERRIDE = "user_override"


@dataclass(frozen=True)
class MergeDecision:
    """Record of how a single field was resolved during merge."""

    field_name: str
    source: MergeSource
    value: str
    reasoning: str
    confidence: Confidence


@dataclass(frozen=True)
class HybridAnalysisResult:
    """Result of hybrid geometry + VLM analysis."""

    building_model: BuildingModel
    geometry_measurements: PageMeasurements
    vlm_result: VlmAnalysisResult
    merge_decisions: list[MergeDecision] = field(
        default_factory=list
    )


class HybridAnalyzer:
    """Merges geometry-computed measurements with VLM semantic analysis.

    Geometry provides precise area/perimeter measurements.
    VLM provides semantic building parameters (type, stories, systems).
    """

    def __init__(
        self,
        measurement_service: MeasurementService,
        vlm_analyzer: VlmAnalyzer,
    ) -> None:
        self._measurement_service = measurement_service
        self._vlm_analyzer = vlm_analyzer

    def analyze(
        self,
        page: fitz.Page,
        image_path: Path,
        context: AnalysisContext | None = None,
    ) -> HybridAnalysisResult:
        """Run both geometry and VLM analysis, then merge results."""
        # Run both analyses
        measurements = self._measurement_service.measure(page)
        vlm_result = self._vlm_analyzer.analyze(
            image_path=image_path,
            context=context,
        )

        # Merge results
        merge_decisions: list[MergeDecision] = []
        merged_model = self._merge(
            measurements, vlm_result, merge_decisions
        )

        return HybridAnalysisResult(
            building_model=merged_model,
            geometry_measurements=measurements,
            vlm_result=vlm_result,
            merge_decisions=merge_decisions,
        )

    def _merge(
        self,
        measurements: PageMeasurements,
        vlm_result: VlmAnalysisResult,
        decisions: list[MergeDecision],
    ) -> BuildingModel:
        """Merge geometry measurements with VLM building model."""
        from cantena.models.building import (
            BuildingModel as _BuildingModel,
        )

        vlm_model = vlm_result.building_model

        # --- gross_sf: prefer geometry if HIGH or MEDIUM confidence ---
        if (
            measurements.gross_area_sf is not None
            and measurements.confidence
            in (
                MeasurementConfidence.HIGH,
                MeasurementConfidence.MEDIUM,
            )
        ):
            gross_sf = measurements.gross_area_sf
            decisions.append(
                MergeDecision(
                    field_name="gross_sf",
                    source=MergeSource.GEOMETRY,
                    value=str(round(gross_sf, 1)),
                    reasoning=(
                        f"Geometry computed {gross_sf:.0f} SF "
                        f"with {measurements.confidence.value} "
                        f"confidence "
                        f"(vs VLM {vlm_model.gross_sf:.0f} SF)"
                    ),
                    confidence=Confidence.HIGH,
                )
            )
            sf_confidence = Confidence.HIGH
        else:
            gross_sf = vlm_model.gross_sf
            reason = (
                "Geometry unavailable or low confidence"
                if measurements.confidence
                in (
                    MeasurementConfidence.NONE,
                    MeasurementConfidence.LOW,
                )
                else "Geometry area not computed"
            )
            decisions.append(
                MergeDecision(
                    field_name="gross_sf",
                    source=MergeSource.VLM,
                    value=str(round(gross_sf, 1)),
                    reasoning=reason,
                    confidence=vlm_model.confidence.get(
                        "gross_sf", Confidence.LOW
                    ),
                )
            )
            sf_confidence = vlm_model.confidence.get(
                "gross_sf", Confidence.LOW
            )

        # --- VLM-only fields ---
        vlm_fields = [
            "building_type",
            "stories",
            "structural_system",
            "exterior_wall_system",
            "story_height_ft",
        ]
        for fname in vlm_fields:
            val = getattr(vlm_model, fname)
            conf = vlm_model.confidence.get(
                fname, Confidence.LOW
            )
            decisions.append(
                MergeDecision(
                    field_name=fname,
                    source=MergeSource.VLM,
                    value=str(val),
                    reasoning=(
                        "Always sourced from VLM semantic analysis"
                    ),
                    confidence=conf,
                )
            )

        # --- special_conditions: merge both ---
        special_conditions = list(vlm_model.special_conditions)
        geom_notes: list[str] = []
        if (
            measurements.confidence == MeasurementConfidence.LOW
            and measurements.gross_area_sf is not None
        ):
            geom_notes.append(
                f"Geometry estimated area: "
                f"{measurements.gross_area_sf:.0f} SF "
                f"(low confidence \u2014 scale estimated)"
            )
        if (
            measurements.gross_area_sf is not None
            and measurements.confidence
            in (
                MeasurementConfidence.HIGH,
                MeasurementConfidence.MEDIUM,
            )
            and abs(
                measurements.gross_area_sf - vlm_model.gross_sf
            )
            > (vlm_model.gross_sf * 0.2)
        ):
            geom_notes.append(
                f"Geometry/VLM area discrepancy: "
                f"geometry={measurements.gross_area_sf:.0f} SF "
                f"vs VLM={vlm_model.gross_sf:.0f} SF"
            )
        special_conditions.extend(geom_notes)

        if geom_notes:
            decisions.append(
                MergeDecision(
                    field_name="special_conditions",
                    source=MergeSource.GEOMETRY,
                    value="; ".join(geom_notes),
                    reasoning=(
                        "Geometry anomalies added to conditions"
                    ),
                    confidence=Confidence.MEDIUM,
                )
            )

        # --- Build merged confidence dict ---
        merged_confidence = dict(vlm_model.confidence)
        merged_confidence["gross_sf"] = sf_confidence

        # --- Construct merged BuildingModel ---
        return _BuildingModel(
            building_type=vlm_model.building_type,
            building_use=vlm_model.building_use,
            gross_sf=gross_sf,
            stories=vlm_model.stories,
            story_height_ft=vlm_model.story_height_ft,
            structural_system=vlm_model.structural_system,
            exterior_wall_system=vlm_model.exterior_wall_system,
            mechanical_system=vlm_model.mechanical_system,
            electrical_service=vlm_model.electrical_service,
            fire_protection=vlm_model.fire_protection,
            location=vlm_model.location,
            complexity_scores=vlm_model.complexity_scores,
            special_conditions=special_conditions,
            confidence=merged_confidence,
        )
