"""Cost estimate output models for the Cantena cost estimation engine."""

from __future__ import annotations

from datetime import datetime

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
