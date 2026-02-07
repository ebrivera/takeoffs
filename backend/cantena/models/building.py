"""Building domain models for the Cantena cost estimation engine."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from cantena.models.enums import (
    BuildingType,
    Confidence,
    ElectricalService,
    ExteriorWall,
    FireProtection,
    MechanicalSystem,
    StructuralSystem,
)


class Location(BaseModel):
    """Geographic location for cost index lookup."""

    city: str
    state: str
    zip_code: str | None = None


class ComplexityScores(BaseModel):
    """Complexity scores (1-5) for different building aspects.

    These scores drive the complexity multiplier applied to the base cost.
    1 = very simple, 3 = typical, 5 = very complex.
    """

    structural: int = Field(default=3, ge=1, le=5)
    mep: int = Field(default=3, ge=1, le=5)
    finishes: int = Field(default=3, ge=1, le=5)
    site: int = Field(default=3, ge=1, le=5)


class BuildingModel(BaseModel):
    """Input model representing a building to be cost-estimated.

    This is the primary input to the cost engine, representing what the VLM
    will eventually extract from construction drawings.
    """

    building_type: BuildingType
    building_use: str
    gross_sf: float = Field(gt=0)
    stories: int = Field(ge=1)
    story_height_ft: float = Field(gt=0, default=10.0)
    structural_system: StructuralSystem
    exterior_wall_system: ExteriorWall
    mechanical_system: MechanicalSystem | None = None
    electrical_service: ElectricalService | None = None
    fire_protection: FireProtection | None = None
    location: Location
    complexity_scores: ComplexityScores = Field(default_factory=ComplexityScores)
    special_conditions: list[str] = Field(default_factory=list)
    confidence: dict[str, Confidence] = Field(default_factory=dict)

    @field_validator("gross_sf")
    @classmethod
    def gross_sf_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            msg = "gross_sf must be positive"
            raise ValueError(msg)
        return v
