"""Cost estimate output models for the Cantena cost estimation engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from cantena.models.enums import Confidence


class CostRange(BaseModel):
    """A cost range with low, expected, and high values.

    We NEVER output a single number — every cost is a range.
    This matches RSMeans ROM estimate accuracy of ±20-25%.
    """

    low: float
    expected: float
    high: float

    @model_validator(mode="after")
    def low_le_expected_le_high(self) -> CostRange:
        if not (self.low <= self.expected <= self.high):
            msg = (
                f"Must satisfy low <= expected <= high, "
                f"got {self.low} <= {self.expected} <= {self.high}"
            )
            raise ValueError(msg)
        return self


class DivisionCost(BaseModel):
    """Cost breakdown for a single CSI division."""

    csi_division: str
    division_name: str
    cost: CostRange
    percent_of_total: float
    source: str


class Assumption(BaseModel):
    """A documented assumption made during estimation."""

    parameter: str
    assumed_value: str
    reasoning: str
    confidence: Confidence


class BuildingSummary(BaseModel):
    """Summary of the building being estimated."""

    building_type: str
    gross_sf: float
    stories: int
    structural_system: str
    exterior_wall: str
    location: str


class EstimateMetadata(BaseModel):
    """Metadata about the estimation run."""

    engine_version: str
    cost_data_version: str
    estimation_method: str = "square_foot_conceptual"


class SpaceCost(BaseModel):
    """Cost breakdown for a single space in a room-type-aware estimate."""

    room_type: str
    name: str
    area_sf: float
    cost_per_sf: CostRange
    total_cost: CostRange
    percent_of_total: float
    source: str


class CostEstimate(BaseModel):
    """Complete cost estimate output from the Cantena engine.

    This is the primary output model, containing the full breakdown
    of costs by CSI division with confidence ranges.
    """

    project_name: str
    building_summary: BuildingSummary
    total_cost: CostRange
    cost_per_sf: CostRange
    breakdown: list[DivisionCost]
    assumptions: list[Assumption]
    generated_at: datetime = Field(default_factory=datetime.now)
    location_factor: float
    metadata: EstimateMetadata
    space_breakdown: list[SpaceCost] | None = None

    def to_summary_dict(self) -> dict[str, Any]:
        """Produce a flat summary dict for frontend consumption.

        Returns a dict with formatted strings for direct display in a React UI.
        """
        from cantena.formatting import format_cost_range, format_currency, format_sf_cost

        top_drivers = sorted(self.breakdown, key=lambda d: d.cost.expected, reverse=True)[:3]

        return {
            "project_name": self.project_name,
            "building_type": self.building_summary.building_type,
            "gross_sf_formatted": f"{self.building_summary.gross_sf:,.0f} SF",
            "total_cost_formatted": format_currency(self.total_cost.expected),
            "total_cost_range_formatted": format_cost_range(self.total_cost),
            "cost_per_sf_formatted": format_currency(self.cost_per_sf.expected),
            "cost_per_sf_range_formatted": format_sf_cost(self.cost_per_sf),
            "location": self.building_summary.location,
            "location_factor": self.location_factor,
            "num_divisions": len(self.breakdown),
            "top_cost_drivers": [
                {
                    "division_name": d.division_name,
                    "cost_formatted": format_cost_range(d.cost),
                    "percent_of_total": d.percent_of_total,
                }
                for d in top_drivers
            ],
            "num_assumptions": len(self.assumptions),
            "generated_at_formatted": self.generated_at.strftime("%Y-%m-%d %H:%M"),
        }

    def to_export_dict(self) -> dict[str, Any]:
        """Produce a detailed dict for Excel/PDF export.

        Returns a dict with full nested data suitable for generating
        detailed export documents.
        """
        return {
            "project_name": self.project_name,
            "building_summary": self.building_summary.model_dump(),
            "total_cost": self.total_cost.model_dump(),
            "cost_per_sf": self.cost_per_sf.model_dump(),
            "breakdown": [
                {
                    "csi_division": d.csi_division,
                    "division_name": d.division_name,
                    "cost": d.cost.model_dump(),
                    "percent_of_total": d.percent_of_total,
                    "source": d.source,
                }
                for d in self.breakdown
            ],
            "assumptions": [
                {
                    "parameter": a.parameter,
                    "assumed_value": a.assumed_value,
                    "reasoning": a.reasoning,
                    "confidence": a.confidence.value,
                }
                for a in self.assumptions
            ],
            "generated_at": self.generated_at.isoformat(),
            "location_factor": self.location_factor,
            "metadata": self.metadata.model_dump(),
        }
