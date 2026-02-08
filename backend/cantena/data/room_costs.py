"""Room-type-level cost data for granular per-room estimates.

Costs are 2025 national averages reflecting the typical cost variation
across different room types within a building.  Kitchen costs more than
a bedroom because of cabinets, counters, plumbing, and appliances;
bathrooms cost more due to fixtures, tile, and plumbing density.
"""

from __future__ import annotations

from pydantic import BaseModel

from cantena.models.enums import BuildingType, RoomType
from cantena.models.estimate import CostRange


class RoomTypeCost(BaseModel):
    """Cost data for a specific room type within a building context."""

    room_type: RoomType
    building_context: BuildingType
    base_cost_per_sf: CostRange
    typical_percent_of_building: float
    cost_drivers: list[str]
    notes: str


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_RESIDENTIAL_CONTEXT = BuildingType.APARTMENT_LOW_RISE

RESIDENTIAL_ROOM_COSTS: list[RoomTypeCost] = [
    RoomTypeCost(
        room_type=RoomType.LIVING_ROOM,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=180.0, expected=215.0, high=250.0),
        typical_percent_of_building=20.0,
        cost_drivers=["flooring", "lighting", "HVAC distribution", "drywall finish"],
        notes="Standard living area with basic finishes",
    ),
    RoomTypeCost(
        room_type=RoomType.KITCHEN,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=250.0, expected=300.0, high=350.0),
        typical_percent_of_building=10.0,
        cost_drivers=[
            "cabinets", "countertops", "appliances", "plumbing fixtures", "ventilation",
        ],
        notes="Kitchen with standard residential appliances and finishes",
    ),
    RoomTypeCost(
        room_type=RoomType.BATHROOM,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=300.0, expected=375.0, high=450.0),
        typical_percent_of_building=5.0,
        cost_drivers=[
            "plumbing fixtures", "tile", "waterproofing", "ventilation", "mirrors",
        ],
        notes="Full bathroom with tub/shower, toilet, and vanity",
    ),
    RoomTypeCost(
        room_type=RoomType.BEDROOM,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=150.0, expected=185.0, high=220.0),
        typical_percent_of_building=20.0,
        cost_drivers=["flooring", "lighting", "closet build-out", "drywall finish"],
        notes="Standard bedroom with closet",
    ),
    RoomTypeCost(
        room_type=RoomType.DINING,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=170.0, expected=205.0, high=240.0),
        typical_percent_of_building=8.0,
        cost_drivers=["flooring", "lighting", "drywall finish"],
        notes="Dining area, similar to living room but typically smaller",
    ),
    RoomTypeCost(
        room_type=RoomType.UTILITY,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=100.0, expected=130.0, high=160.0),
        typical_percent_of_building=3.0,
        cost_drivers=["mechanical equipment", "electrical panel", "basic finishes"],
        notes="Utility/mechanical room with basic finishes",
    ),
    RoomTypeCost(
        room_type=RoomType.LAUNDRY,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=120.0, expected=150.0, high=180.0),
        typical_percent_of_building=3.0,
        cost_drivers=["plumbing hookups", "dryer vent", "flooring", "cabinetry"],
        notes="Laundry room with washer/dryer hookups",
    ),
    RoomTypeCost(
        room_type=RoomType.PORCH,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=80.0, expected=105.0, high=130.0),
        typical_percent_of_building=5.0,
        cost_drivers=["decking", "railing", "roofing", "columns"],
        notes="Covered porch or deck",
    ),
    RoomTypeCost(
        room_type=RoomType.GARAGE,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=60.0, expected=80.0, high=100.0),
        typical_percent_of_building=12.0,
        cost_drivers=["slab", "garage door", "basic electrical", "insulation"],
        notes="Attached garage with slab-on-grade",
    ),
    RoomTypeCost(
        room_type=RoomType.CLOSET,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=100.0, expected=125.0, high=150.0),
        typical_percent_of_building=4.0,
        cost_drivers=["shelving", "flooring", "lighting", "drywall"],
        notes="Walk-in or standard closet with shelving",
    ),
    RoomTypeCost(
        room_type=RoomType.HALLWAY,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=140.0, expected=170.0, high=200.0),
        typical_percent_of_building=5.0,
        cost_drivers=["flooring", "lighting", "drywall finish"],
        notes="Interior hallway/corridor",
    ),
    RoomTypeCost(
        room_type=RoomType.ENTRY,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=180.0, expected=215.0, high=250.0),
        typical_percent_of_building=2.0,
        cost_drivers=["flooring", "lighting", "entry door", "trim work"],
        notes="Entry/foyer area",
    ),
    RoomTypeCost(
        room_type=RoomType.OTHER,
        building_context=_RESIDENTIAL_CONTEXT,
        base_cost_per_sf=CostRange(low=150.0, expected=185.0, high=220.0),
        typical_percent_of_building=3.0,
        cost_drivers=["general construction", "finishes"],
        notes="Fallback rate for unclassified residential rooms",
    ),
]

_OFFICE_CONTEXT = BuildingType.OFFICE_LOW_RISE

OFFICE_ROOM_COSTS: list[RoomTypeCost] = [
    RoomTypeCost(
        room_type=RoomType.LOBBY,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=300.0, expected=350.0, high=400.0),
        typical_percent_of_building=5.0,
        cost_drivers=[
            "premium finishes", "lighting design", "security systems", "reception desk",
        ],
        notes="Main lobby/reception with premium finishes",
    ),
    RoomTypeCost(
        room_type=RoomType.OPEN_OFFICE,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=200.0, expected=240.0, high=280.0),
        typical_percent_of_building=45.0,
        cost_drivers=[
            "raised floor", "data cabling", "HVAC", "lighting", "ceiling grid",
        ],
        notes="Open office area with standard commercial finishes",
    ),
    RoomTypeCost(
        room_type=RoomType.CORRIDOR,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=150.0, expected=175.0, high=200.0),
        typical_percent_of_building=12.0,
        cost_drivers=["flooring", "lighting", "fire protection", "wayfinding"],
        notes="Common corridors and circulation",
    ),
    RoomTypeCost(
        room_type=RoomType.RESTROOM,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=350.0, expected=425.0, high=500.0),
        typical_percent_of_building=4.0,
        cost_drivers=[
            "plumbing fixtures", "tile", "partitions", "ventilation", "ADA compliance",
        ],
        notes="Commercial restroom with ADA-compliant fixtures",
    ),
    RoomTypeCost(
        room_type=RoomType.CONFERENCE,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=250.0, expected=300.0, high=350.0),
        typical_percent_of_building=8.0,
        cost_drivers=[
            "AV systems", "acoustic treatment", "lighting controls", "premium finishes",
        ],
        notes="Conference room with AV and acoustic treatment",
    ),
    RoomTypeCost(
        room_type=RoomType.MECHANICAL_ROOM,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=120.0, expected=150.0, high=180.0),
        typical_percent_of_building=6.0,
        cost_drivers=[
            "HVAC equipment", "electrical switchgear", "fire suppression", "ventilation",
        ],
        notes="Mechanical/electrical room with equipment",
    ),
    RoomTypeCost(
        room_type=RoomType.PRIVATE_OFFICE,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=230.0, expected=270.0, high=310.0),
        typical_percent_of_building=10.0,
        cost_drivers=[
            "partitions", "door hardware", "lighting", "data cabling", "acoustic treatment",
        ],
        notes="Private office with walls and door",
    ),
    RoomTypeCost(
        room_type=RoomType.KITCHEN_BREAK,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=250.0, expected=300.0, high=350.0),
        typical_percent_of_building=3.0,
        cost_drivers=[
            "cabinets", "countertops", "appliances", "plumbing", "ventilation",
        ],
        notes="Office kitchen/break room",
    ),
    RoomTypeCost(
        room_type=RoomType.OTHER,
        building_context=_OFFICE_CONTEXT,
        base_cost_per_sf=CostRange(low=185.0, expected=225.0, high=275.0),
        typical_percent_of_building=7.0,
        cost_drivers=["general construction", "finishes"],
        notes="Fallback rate for unclassified office rooms",
    ),
]

_SCHOOL_CONTEXT = BuildingType.SCHOOL_ELEMENTARY

SCHOOL_ROOM_COSTS: list[RoomTypeCost] = [
    RoomTypeCost(
        room_type=RoomType.CLASSROOM,
        building_context=_SCHOOL_CONTEXT,
        base_cost_per_sf=CostRange(low=250.0, expected=300.0, high=350.0),
        typical_percent_of_building=50.0,
        cost_drivers=[
            "acoustic treatment", "lighting", "data/AV", "durable finishes", "casework",
        ],
        notes="Standard classroom with teaching wall and casework",
    ),
    RoomTypeCost(
        room_type=RoomType.CORRIDOR,
        building_context=_SCHOOL_CONTEXT,
        base_cost_per_sf=CostRange(low=180.0, expected=200.0, high=220.0),
        typical_percent_of_building=15.0,
        cost_drivers=[
            "durable flooring", "lockers", "lighting", "fire protection", "wayfinding",
        ],
        notes="School corridor with lockers and durable finishes",
    ),
    RoomTypeCost(
        room_type=RoomType.OTHER,
        building_context=_SCHOOL_CONTEXT,
        base_cost_per_sf=CostRange(low=215.0, expected=265.0, high=330.0),
        typical_percent_of_building=35.0,
        cost_drivers=["general construction", "finishes"],
        notes="Fallback rate for unclassified school rooms",
    ),
]

_HOSPITAL_CONTEXT = BuildingType.HOSPITAL

HOSPITAL_ROOM_COSTS: list[RoomTypeCost] = [
    RoomTypeCost(
        room_type=RoomType.PATIENT_ROOM,
        building_context=_HOSPITAL_CONTEXT,
        base_cost_per_sf=CostRange(low=400.0, expected=500.0, high=600.0),
        typical_percent_of_building=35.0,
        cost_drivers=[
            "medical gases", "nurse call", "infection control finishes",
            "headwall systems", "bathroom per room",
        ],
        notes="Standard patient room with private bathroom",
    ),
    RoomTypeCost(
        room_type=RoomType.OPERATING_ROOM,
        building_context=_HOSPITAL_CONTEXT,
        base_cost_per_sf=CostRange(low=800.0, expected=1000.0, high=1200.0),
        typical_percent_of_building=10.0,
        cost_drivers=[
            "surgical lighting", "medical gas columns", "HEPA filtration",
            "seamless flooring", "equipment booms", "laminar flow",
        ],
        notes="Surgical suite with specialty HVAC and medical gas systems",
    ),
    RoomTypeCost(
        room_type=RoomType.OTHER,
        building_context=_HOSPITAL_CONTEXT,
        base_cost_per_sf=CostRange(low=380.0, expected=470.0, high=580.0),
        typical_percent_of_building=55.0,
        cost_drivers=["general construction", "clinical finishes"],
        notes="Fallback rate for unclassified hospital rooms",
    ),
]

# ---------------------------------------------------------------------------
# Master lookup: building type -> list of room costs
# ---------------------------------------------------------------------------

_RESIDENTIAL_TYPES = frozenset({
    BuildingType.APARTMENT_LOW_RISE,
    BuildingType.APARTMENT_MID_RISE,
    BuildingType.APARTMENT_HIGH_RISE,
    BuildingType.HOTEL,
})

_OFFICE_TYPES = frozenset({
    BuildingType.OFFICE_LOW_RISE,
    BuildingType.OFFICE_MID_RISE,
    BuildingType.OFFICE_HIGH_RISE,
    BuildingType.RETAIL,
    BuildingType.WAREHOUSE,
})

_SCHOOL_TYPES = frozenset({
    BuildingType.SCHOOL_ELEMENTARY,
    BuildingType.SCHOOL_HIGH,
})


def get_room_costs_for_building_type(
    building_type: BuildingType,
) -> list[RoomTypeCost]:
    """Return room-type costs appropriate for the given building type."""
    if building_type in _RESIDENTIAL_TYPES:
        return list(RESIDENTIAL_ROOM_COSTS)
    if building_type in _OFFICE_TYPES:
        return list(OFFICE_ROOM_COSTS)
    if building_type in _SCHOOL_TYPES:
        return list(SCHOOL_ROOM_COSTS)
    if building_type == BuildingType.HOSPITAL:
        return list(HOSPITAL_ROOM_COSTS)
    # Fallback: return residential as the most common default
    return list(RESIDENTIAL_ROOM_COSTS)
