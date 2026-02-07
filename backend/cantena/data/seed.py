"""Seed cost data for the Cantena cost estimation engine.

Costs are 2025 national averages based on publicly available
RSMeans square foot cost data and ENR construction cost indexes.
"""

from cantena.data.building_costs import SquareFootCostEntry
from cantena.models.enums import BuildingType, ExteriorWall, StructuralSystem
from cantena.models.estimate import CostRange

SEED_COST_ENTRIES: list[SquareFootCostEntry] = [
    # --- Apartments ---
    SquareFootCostEntry(
        building_type=BuildingType.APARTMENT_LOW_RISE,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall=ExteriorWall.BRICK_VENEER,
        stories_range=(1, 3),
        cost_per_sf=CostRange(low=165.0, expected=195.0, high=240.0),
        year=2025,
        notes="Wood-frame low-rise apartment, brick veneer, 1-3 stories",
    ),
    SquareFootCostEntry(
        building_type=BuildingType.APARTMENT_LOW_RISE,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall=ExteriorWall.WOOD_SIDING,
        stories_range=(1, 3),
        cost_per_sf=CostRange(low=145.0, expected=175.0, high=215.0),
        year=2025,
        notes="Wood-frame low-rise apartment, wood siding, 1-3 stories",
    ),
    SquareFootCostEntry(
        building_type=BuildingType.APARTMENT_MID_RISE,
        structural_system=StructuralSystem.CONCRETE_FRAME,
        exterior_wall=ExteriorWall.BRICK_VENEER,
        stories_range=(4, 7),
        cost_per_sf=CostRange(low=195.0, expected=240.0, high=295.0),
        year=2025,
        notes="Concrete-frame mid-rise apartment, brick veneer, 4-7 stories",
    ),
    SquareFootCostEntry(
        building_type=BuildingType.APARTMENT_HIGH_RISE,
        structural_system=StructuralSystem.CONCRETE_FRAME,
        exterior_wall=ExteriorWall.CURTAIN_WALL,
        stories_range=(8, 30),
        cost_per_sf=CostRange(low=280.0, expected=340.0, high=420.0),
        year=2025,
        notes="Concrete-frame high-rise apartment, curtain wall, 8-30 stories",
    ),
    # --- Offices ---
    SquareFootCostEntry(
        building_type=BuildingType.OFFICE_LOW_RISE,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall=ExteriorWall.BRICK_VENEER,
        stories_range=(1, 3),
        cost_per_sf=CostRange(low=185.0, expected=225.0, high=275.0),
        year=2025,
        notes="Steel-frame low-rise office, brick veneer, 1-3 stories",
    ),
    SquareFootCostEntry(
        building_type=BuildingType.OFFICE_MID_RISE,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall=ExteriorWall.CURTAIN_WALL,
        stories_range=(4, 7),
        cost_per_sf=CostRange(low=235.0, expected=285.0, high=350.0),
        year=2025,
        notes="Steel-frame mid-rise office, curtain wall, 4-7 stories",
    ),
    SquareFootCostEntry(
        building_type=BuildingType.OFFICE_HIGH_RISE,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall=ExteriorWall.CURTAIN_WALL,
        stories_range=(8, 30),
        cost_per_sf=CostRange(low=295.0, expected=360.0, high=440.0),
        year=2025,
        notes="Steel-frame high-rise office, curtain wall, 8-30 stories",
    ),
    # --- Retail ---
    SquareFootCostEntry(
        building_type=BuildingType.RETAIL,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall=ExteriorWall.EIFS,
        stories_range=(1, 2),
        cost_per_sf=CostRange(low=130.0, expected=165.0, high=210.0),
        year=2025,
        notes="Steel-frame retail, EIFS exterior, 1-2 stories",
    ),
    SquareFootCostEntry(
        building_type=BuildingType.RETAIL,
        structural_system=StructuralSystem.MASONRY_BEARING,
        exterior_wall=ExteriorWall.BRICK_VENEER,
        stories_range=(1, 2),
        cost_per_sf=CostRange(low=145.0, expected=180.0, high=225.0),
        year=2025,
        notes="Masonry retail, brick veneer, 1-2 stories",
    ),
    # --- Warehouse ---
    SquareFootCostEntry(
        building_type=BuildingType.WAREHOUSE,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall=ExteriorWall.METAL_PANEL,
        stories_range=(1, 1),
        cost_per_sf=CostRange(low=85.0, expected=115.0, high=150.0),
        year=2025,
        notes="Steel-frame warehouse, metal panel, single story",
    ),
    SquareFootCostEntry(
        building_type=BuildingType.WAREHOUSE,
        structural_system=StructuralSystem.PRECAST_CONCRETE,
        exterior_wall=ExteriorWall.PRECAST_PANEL,
        stories_range=(1, 2),
        cost_per_sf=CostRange(low=105.0, expected=140.0, high=180.0),
        year=2025,
        notes="Precast warehouse, precast panel, 1-2 stories",
    ),
    # --- Schools ---
    SquareFootCostEntry(
        building_type=BuildingType.SCHOOL_ELEMENTARY,
        structural_system=StructuralSystem.MASONRY_BEARING,
        exterior_wall=ExteriorWall.BRICK_VENEER,
        stories_range=(1, 2),
        cost_per_sf=CostRange(low=215.0, expected=265.0, high=330.0),
        year=2025,
        notes="Masonry elementary school, brick veneer, 1-2 stories",
    ),
    SquareFootCostEntry(
        building_type=BuildingType.SCHOOL_HIGH,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall=ExteriorWall.BRICK_VENEER,
        stories_range=(2, 4),
        cost_per_sf=CostRange(low=240.0, expected=295.0, high=365.0),
        year=2025,
        notes="Steel-frame high school, brick veneer, 2-4 stories",
    ),
    # --- Hospital ---
    SquareFootCostEntry(
        building_type=BuildingType.HOSPITAL,
        structural_system=StructuralSystem.CONCRETE_FRAME,
        exterior_wall=ExteriorWall.CURTAIN_WALL,
        stories_range=(2, 10),
        cost_per_sf=CostRange(low=380.0, expected=470.0, high=580.0),
        year=2025,
        notes="Concrete-frame hospital, curtain wall, 2-10 stories",
    ),
    # --- Hotel ---
    SquareFootCostEntry(
        building_type=BuildingType.HOTEL,
        structural_system=StructuralSystem.CONCRETE_FRAME,
        exterior_wall=ExteriorWall.BRICK_VENEER,
        stories_range=(3, 15),
        cost_per_sf=CostRange(low=200.0, expected=250.0, high=310.0),
        year=2025,
        notes="Concrete-frame hotel, brick veneer, 3-15 stories",
    ),
    # --- Additional entries for fuzzy match coverage ---
    SquareFootCostEntry(
        building_type=BuildingType.OFFICE_LOW_RISE,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall=ExteriorWall.WOOD_SIDING,
        stories_range=(1, 3),
        cost_per_sf=CostRange(low=160.0, expected=200.0, high=245.0),
        year=2025,
        notes="Wood-frame low-rise office, wood siding, 1-3 stories",
    ),
]
