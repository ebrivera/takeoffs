"""Core cost estimation engine for the Cantena cost estimation library.

The CostEngine implements a square-foot conceptual estimation methodology:

1. **Base cost lookup** — Find the $/SF for the building type, structural system,
   and exterior wall from the cost data repository (with fuzzy fallback).
2. **Location adjustment** — Multiply by the city/state cost index to regionalize.
3. **Complexity adjustment** — Apply a weighted complexity multiplier derived from
   the building's complexity scores (structural, MEP, finishes, site).
4. **Range generation** — Produce low/expected/high values (expected * 0.80 to
   expected * 1.25) matching RSMeans ROM estimate accuracy of ±20-25%.
5. **CSI division breakdown** — Distribute the total across CSI divisions using
   typical percentage breakdowns by building type.
6. **Assumption documentation** — Record every fuzzy match, low-confidence field,
   and default used so estimates are transparent and traceable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cantena.data.csi_divisions import CSI_DIVISIONS, DIVISION_DESCRIPTIONS
from cantena.models.enums import Confidence
from cantena.models.estimate import (
    Assumption,
    BuildingSummary,
    CostEstimate,
    CostRange,
    DivisionCost,
    EstimateMetadata,
    GeometryRef,
    SpaceCost,
)

if TYPE_CHECKING:
    from cantena.data.repository import CostDataRepository
    from cantena.geometry.rooms import DetectedRoom
    from cantena.geometry.walls import WallSegment
    from cantena.models.building import BuildingModel
    from cantena.models.space_program import SpaceProgram

# Complexity score -> multiplier mapping
_COMPLEXITY_MULTIPLIERS: dict[int, float] = {
    1: 0.85,
    2: 0.95,
    3: 1.00,
    4: 1.10,
    5: 1.25,
}

# Weights for each complexity dimension
_COMPLEXITY_WEIGHTS: dict[str, float] = {
    "structural": 0.30,
    "mep": 0.30,
    "finishes": 0.25,
    "site": 0.15,
}

ENGINE_VERSION = "0.1.0"
COST_DATA_VERSION = "2025.1"


class CostEngine:
    """Core estimation engine that converts a BuildingModel into a CostEstimate.

    Args:
        repository: The cost data repository providing lookup methods for
            base costs, CSI division breakdowns, and city cost indexes.

    Example::

        from cantena.data.repository import CostDataRepository
        from cantena.data.seed import SEED_COST_ENTRIES

        repo = CostDataRepository(SEED_COST_ENTRIES)
        engine = CostEngine(repo)
        estimate = engine.estimate(building, "My Project")
    """

    def __init__(self, repository: CostDataRepository) -> None:
        self._repository = repository

    def estimate(
        self,
        building: BuildingModel,
        project_name: str,
        space_program: SpaceProgram | None = None,
        rooms: list[DetectedRoom] | None = None,
        wall_segments: list[WallSegment] | None = None,
        outer_boundary: list[tuple[float, float]] | None = None,
        gross_sf_override: float | None = None,
        perimeter_lf: float | None = None,
    ) -> CostEstimate:
        """Produce a conceptual cost estimate for a building.

        Args:
            building: The building model describing the structure to estimate.
            project_name: A human-readable name for the project.
            space_program: Optional room-by-room program for per-room pricing.
                When provided, each room type is priced using room-specific
                $/SF data and the total is the sum of individual room costs.

        Returns:
            A complete CostEstimate with total cost, cost per SF, CSI division
            breakdown, and documented assumptions.

        Raises:
            ValueError: If no cost data match is found for the building type.
        """
        assumptions: list[Assumption] = []

        # 1. Look up base $/SF (with fuzzy fallback)
        entry, fallback_reasons = self._repository.get_best_match_sf_cost(
            building_type=building.building_type,
            structural_system=building.structural_system,
            exterior_wall=building.exterior_wall_system,
            stories=building.stories,
        )

        for reason in fallback_reasons:
            assumptions.append(
                Assumption(
                    parameter="cost_data_match",
                    assumed_value=str(entry.cost_per_sf.expected),
                    reasoning=reason,
                    confidence=Confidence.MEDIUM,
                )
            )

        base_cost_per_sf = entry.cost_per_sf.expected

        # 2. Apply location factor
        location_factor = self._repository.get_city_cost_index(
            city=building.location.city,
            state=building.location.state,
        )
        adjusted_cost_per_sf = base_cost_per_sf * location_factor

        # 3. Apply complexity multiplier
        complexity_multiplier = self._calculate_complexity_multiplier(building)
        adjusted_cost_per_sf *= complexity_multiplier

        # 4. Generate cost ranges (room-type-aware if space_program provided)
        space_breakdown: list[SpaceCost] | None = None

        if space_program is not None:
            total_cost, cost_per_sf, space_breakdown = (
                self._estimate_with_space_program(
                    space_program=space_program,
                    building=building,
                    location_factor=location_factor,
                    complexity_multiplier=complexity_multiplier,
                    fallback_cost_per_sf=adjusted_cost_per_sf,
                )
            )
        else:
            total_expected = adjusted_cost_per_sf * building.gross_sf
            total_cost = CostRange(
                low=total_expected * 0.80,
                expected=total_expected,
                high=total_expected * 1.25,
            )
            cost_per_sf = CostRange(
                low=adjusted_cost_per_sf * 0.80,
                expected=adjusted_cost_per_sf,
                high=adjusted_cost_per_sf * 1.25,
            )

        # 5. Break down into CSI divisions
        breakdown = self._generate_division_breakdown(
            building=building,
            total_cost=total_cost,
            location_factor=location_factor,
            complexity_multiplier=complexity_multiplier,
            rooms=rooms,
            wall_segments=wall_segments,
            outer_boundary=outer_boundary,
            gross_sf=gross_sf_override or building.gross_sf,
            perimeter_lf=perimeter_lf,
        )

        # 6. Document low-confidence field assumptions
        self._collect_confidence_assumptions(building, assumptions)

        # 7. Build summary and metadata
        building_summary = BuildingSummary(
            building_type=building.building_type.value,
            gross_sf=building.gross_sf,
            stories=building.stories,
            structural_system=building.structural_system.value,
            exterior_wall=building.exterior_wall_system.value,
            location=f"{building.location.city}, {building.location.state}",
        )

        metadata = EstimateMetadata(
            engine_version=ENGINE_VERSION,
            cost_data_version=COST_DATA_VERSION,
            building_type_model=entry.notes,
        )

        return CostEstimate(
            project_name=project_name,
            building_summary=building_summary,
            total_cost=total_cost,
            cost_per_sf=cost_per_sf,
            breakdown=breakdown,
            assumptions=assumptions,
            location_factor=location_factor,
            metadata=metadata,
            space_breakdown=space_breakdown,
        )

    def _estimate_with_space_program(
        self,
        space_program: SpaceProgram,
        building: BuildingModel,
        location_factor: float,
        complexity_multiplier: float,
        fallback_cost_per_sf: float,
    ) -> tuple[CostRange, CostRange, list[SpaceCost]]:
        """Price each room type separately using room-specific $/SF data.

        Returns (total_cost, cost_per_sf, space_breakdown).
        """
        from cantena.data.room_costs import get_room_costs_for_building_type

        room_costs = get_room_costs_for_building_type(building.building_type)
        cost_by_room_type = {rc.room_type: rc.base_cost_per_sf for rc in room_costs}

        space_costs: list[SpaceCost] = []
        total_expected = 0.0
        total_low = 0.0
        total_high = 0.0

        for space in space_program.spaces:
            area = space.area_sf * space.count

            # Look up room-type-specific cost; fall back to whole-building rate
            room_cost_range = cost_by_room_type.get(space.room_type)
            if room_cost_range is not None:
                adj_low = room_cost_range.low * location_factor * complexity_multiplier
                adj_expected = room_cost_range.expected * location_factor * complexity_multiplier
                adj_high = room_cost_range.high * location_factor * complexity_multiplier
            else:
                # Fallback: whole-building $/SF with standard range
                adj_expected = fallback_cost_per_sf
                adj_low = fallback_cost_per_sf * 0.80
                adj_high = fallback_cost_per_sf * 1.25

            room_total_low = adj_low * area
            room_total_expected = adj_expected * area
            room_total_high = adj_high * area

            total_low += room_total_low
            total_expected += room_total_expected
            total_high += room_total_high

            space_costs.append(SpaceCost(
                room_type=space.room_type.value,
                name=space.name,
                area_sf=area,
                cost_per_sf=CostRange(
                    low=adj_low,
                    expected=adj_expected,
                    high=adj_high,
                ),
                total_cost=CostRange(
                    low=room_total_low,
                    expected=room_total_expected,
                    high=room_total_high,
                ),
                percent_of_total=0.0,  # Computed below
                source=space.source.value,
            ))

        # Compute percent_of_total for each space
        if total_expected > 0:
            for sc in space_costs:
                sc.percent_of_total = (
                    sc.total_cost.expected / total_expected * 100.0
                )

        total_area = space_program.total_area_sf
        avg_cost_per_sf = total_expected / total_area if total_area > 0 else 0.0

        total_cost = CostRange(
            low=total_low,
            expected=total_expected,
            high=total_high,
        )
        cost_per_sf = CostRange(
            low=total_low / total_area if total_area > 0 else 0.0,
            expected=avg_cost_per_sf,
            high=total_high / total_area if total_area > 0 else 0.0,
        )

        return total_cost, cost_per_sf, space_costs

    def _calculate_complexity_multiplier(self, building: BuildingModel) -> float:
        """Calculate the weighted complexity multiplier from complexity scores."""
        scores = building.complexity_scores
        weighted_sum = (
            _COMPLEXITY_WEIGHTS["structural"] * _COMPLEXITY_MULTIPLIERS[scores.structural]
            + _COMPLEXITY_WEIGHTS["mep"] * _COMPLEXITY_MULTIPLIERS[scores.mep]
            + _COMPLEXITY_WEIGHTS["finishes"] * _COMPLEXITY_MULTIPLIERS[scores.finishes]
            + _COMPLEXITY_WEIGHTS["site"] * _COMPLEXITY_MULTIPLIERS[scores.site]
        )
        return weighted_sum

    def _generate_division_breakdown(
        self,
        building: BuildingModel,
        total_cost: CostRange,
        location_factor: float = 1.0,
        complexity_multiplier: float = 1.0,
        rooms: list[DetectedRoom] | None = None,
        wall_segments: list[WallSegment] | None = None,
        outer_boundary: list[tuple[float, float]] | None = None,
        gross_sf: float | None = None,
        perimeter_lf: float | None = None,
    ) -> list[DivisionCost]:
        """Break down total cost into CSI division costs."""
        percentages = self._repository.get_division_breakdown(building.building_type)
        effective_sf = gross_sf or building.gross_sf

        # Build a name lookup from CSI_DIVISIONS
        division_names: dict[str, str] = {
            d.number: d.name for d in CSI_DIVISIONS
        }

        breakdown: list[DivisionCost] = []
        for division_number, pct in sorted(percentages.items()):
            division_name = division_names.get(division_number, f"Division {division_number}")
            fraction = pct / 100.0
            division_cost = CostRange(
                low=total_cost.low * fraction,
                expected=total_cost.expected * fraction,
                high=total_cost.high * fraction,
            )

            # Compute pricing derivation fields for transparency
            adjusted_rate: float | None = None
            base_rate: float | None = None
            if effective_sf > 0:
                adjusted_rate = division_cost.expected / effective_sf
                combined_factor = location_factor * complexity_multiplier
                base_rate = (
                    adjusted_rate / combined_factor if combined_factor != 0 else adjusted_rate
                )

            breakdown.append(
                DivisionCost(
                    csi_division=division_number,
                    division_name=division_name,
                    cost=division_cost,
                    percent_of_total=pct,
                    source="RSMeans 2025 national average",
                    base_rate=base_rate,
                    location_factor=location_factor,
                    adjusted_rate=adjusted_rate,
                    includes_description=DIVISION_DESCRIPTIONS.get(division_number),
                    rate_source="RSMeans Square Foot Models",
                )
            )

        # Attach geometry references if geometry is available
        if rooms or wall_segments or outer_boundary:
            breakdown = self._attach_geometry_refs(
                breakdown,
                rooms=rooms,
                wall_segments=wall_segments,
                outer_boundary=outer_boundary,
                gross_sf=gross_sf or building.gross_sf,
                perimeter_lf=perimeter_lf,
            )

        return breakdown

    @staticmethod
    def _attach_geometry_refs(
        breakdown: list[DivisionCost],
        rooms: list[DetectedRoom] | None = None,
        wall_segments: list[WallSegment] | None = None,
        outer_boundary: list[tuple[float, float]] | None = None,
        gross_sf: float = 0.0,
        perimeter_lf: float | None = None,
    ) -> list[DivisionCost]:
        """Attach geometry references and quantity metadata to divisions.

        This maps CSI divisions to their source geometry (rooms, walls,
        or footprint) and computes unit costs. It does NOT change the
        cost calculations — only adds traceability metadata.
        """
        wall_divisions = {"04", "07"}
        room_divisions = {"06", "09", "23"}
        wet_room_labels = {
            "kitchen", "wc", "bathroom", "restroom",
            "laundry", "utility", "mechanical",
        }

        # Build geometry refs for each type
        room_refs: list[GeometryRef] = []
        room_area_sf = 0.0
        wet_room_refs: list[GeometryRef] = []
        wet_room_area_sf = 0.0
        if rooms:
            for r in rooms:
                ref = GeometryRef(
                    ref_id=f"room-{r.room_index}",
                    ref_type="room_polygon",
                    coordinates=[list(pt) for pt in r.polygon_pts],
                    label=r.label,
                )
                room_refs.append(ref)
                if r.area_sf is not None:
                    room_area_sf += r.area_sf
                # Classify wet rooms by label
                if r.label and r.label.lower() in wet_room_labels:
                    wet_room_refs.append(ref)
                    if r.area_sf is not None:
                        wet_room_area_sf += r.area_sf

        wall_refs: list[GeometryRef] = []
        if wall_segments:
            for i, seg in enumerate(wall_segments):
                wall_refs.append(GeometryRef(
                    ref_id=f"wall-{i}",
                    ref_type="wall_segment",
                    coordinates=[
                        [seg.start.x, seg.start.y],
                        [seg.end.x, seg.end.y],
                    ],
                ))

        footprint_refs: list[GeometryRef] = []
        if outer_boundary:
            footprint_refs.append(GeometryRef(
                ref_id="footprint",
                ref_type="building_footprint",
                coordinates=[list(pt) for pt in outer_boundary],
            ))

        updated: list[DivisionCost] = []
        for div in breakdown:
            div_num = div.csi_division
            refs: list[GeometryRef] = []
            quantity: float | None = None
            unit: str | None = None
            quantity_source: str | None = None

            if div_num in wall_divisions and wall_refs:
                refs = wall_refs
                quantity = perimeter_lf if perimeter_lf and perimeter_lf > 0 else None
                unit = "LF"
                quantity_source = "Measured from drawing geometry"
            elif div_num == "22" and wet_room_refs:
                refs = wet_room_refs
                quantity = wet_room_area_sf if wet_room_area_sf > 0 else None
                unit = "SF"
                quantity_source = "Measured from drawing geometry"
            elif div_num in room_divisions and room_refs:
                refs = room_refs
                quantity = room_area_sf if room_area_sf > 0 else None
                unit = "SF"
                quantity_source = "Measured from drawing geometry"
            elif footprint_refs:
                refs = footprint_refs
                quantity = gross_sf if gross_sf > 0 else None
                unit = "SF"
                quantity_source = "Calculated from building footprint"

            unit_cost: float | None = None
            total_cost: float | None = div.cost.expected if refs else None
            if quantity and quantity > 0 and total_cost:
                unit_cost = total_cost / quantity

            updated.append(DivisionCost(
                csi_division=div.csi_division,
                division_name=div.division_name,
                cost=div.cost,
                percent_of_total=div.percent_of_total,
                source=div.source,
                quantity=quantity,
                unit=unit,
                unit_cost=unit_cost,
                total_cost=total_cost,
                geometry_refs=refs,
                base_rate=div.base_rate,
                location_factor=div.location_factor,
                adjusted_rate=div.adjusted_rate,
                quantity_source=quantity_source or div.quantity_source,
                includes_description=div.includes_description,
                rate_source=div.rate_source,
            ))

        return updated

    def _collect_confidence_assumptions(
        self,
        building: BuildingModel,
        assumptions: list[Assumption],
    ) -> None:
        """Add assumptions for any fields with low or medium confidence."""
        for field_name, confidence in building.confidence.items():
            if confidence == Confidence.LOW:
                field_value = getattr(building, field_name, None)
                assumptions.append(
                    Assumption(
                        parameter=field_name,
                        assumed_value=str(field_value) if field_value is not None else "unknown",
                        reasoning=f"Field '{field_name}' was extracted with low confidence",
                        confidence=Confidence.LOW,
                    )
                )
