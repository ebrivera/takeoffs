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

from cantena.data.csi_divisions import CSI_DIVISIONS
from cantena.models.enums import Confidence
from cantena.models.estimate import (
    Assumption,
    BuildingSummary,
    CostEstimate,
    CostRange,
    DivisionCost,
    EstimateMetadata,
)

if TYPE_CHECKING:
    from cantena.data.repository import CostDataRepository
    from cantena.models.building import BuildingModel

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

    def estimate(self, building: BuildingModel, project_name: str) -> CostEstimate:
        """Produce a conceptual cost estimate for a building.

        Args:
            building: The building model describing the structure to estimate.
            project_name: A human-readable name for the project.

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

        # 4. Generate cost ranges
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
        )

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
    ) -> list[DivisionCost]:
        """Break down total cost into CSI division costs."""
        percentages = self._repository.get_division_breakdown(building.building_type)

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
            breakdown.append(
                DivisionCost(
                    csi_division=division_number,
                    division_name=division_name,
                    cost=division_cost,
                    percent_of_total=pct,
                    source="RSMeans 2025 national average",
                )
            )

        return breakdown

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
