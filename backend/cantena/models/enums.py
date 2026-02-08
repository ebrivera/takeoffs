"""Enums for the Cantena domain models.

These enums represent the RSMeans square foot estimator input parameters
mapped to the Cantena domain.
"""

from enum import StrEnum


class BuildingType(StrEnum):
    """Common building types from RSMeans square foot cost models."""

    APARTMENT_LOW_RISE = "apartment_low_rise"
    APARTMENT_MID_RISE = "apartment_mid_rise"
    APARTMENT_HIGH_RISE = "apartment_high_rise"
    OFFICE_LOW_RISE = "office_low_rise"
    OFFICE_MID_RISE = "office_mid_rise"
    OFFICE_HIGH_RISE = "office_high_rise"
    RETAIL = "retail"
    WAREHOUSE = "warehouse"
    SCHOOL_ELEMENTARY = "school_elementary"
    SCHOOL_HIGH = "school_high"
    HOSPITAL = "hospital"
    HOTEL = "hotel"


class StructuralSystem(StrEnum):
    """Primary structural system classifications."""

    WOOD_FRAME = "wood_frame"
    STEEL_FRAME = "steel_frame"
    CONCRETE_FRAME = "concrete_frame"
    MASONRY_BEARING = "masonry_bearing"
    PRECAST_CONCRETE = "precast_concrete"


class ExteriorWall(StrEnum):
    """Exterior wall / cladding system types."""

    BRICK_VENEER = "brick_veneer"
    CURTAIN_WALL = "curtain_wall"
    METAL_PANEL = "metal_panel"
    PRECAST_PANEL = "precast_panel"
    STUCCO = "stucco"
    WOOD_SIDING = "wood_siding"
    EIFS = "eifs"


class MechanicalSystem(StrEnum):
    """HVAC / mechanical system classifications."""

    SPLIT_SYSTEM = "split_system"
    PACKAGED_ROOFTOP = "packaged_rooftop"
    CHILLED_WATER = "chilled_water"
    VAV = "vav"
    VRF = "vrf"


class ElectricalService(StrEnum):
    """Electrical service level classifications."""

    LIGHT = "light"
    STANDARD = "standard"
    HEAVY = "heavy"


class FireProtection(StrEnum):
    """Fire protection system types."""

    NONE = "none"
    SPRINKLER_WET = "sprinkler_wet"
    SPRINKLER_COMBINED = "sprinkler_combined"


class RoomType(StrEnum):
    """Room types for room-level cost differentiation."""

    # Residential
    LIVING_ROOM = "living_room"
    KITCHEN = "kitchen"
    DINING = "dining"
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    RESTROOM = "restroom"
    WC = "wc"
    UTILITY = "utility"
    LAUNDRY = "laundry"
    CLOSET = "closet"
    PORCH = "porch"

    # Commercial / shared
    LOBBY = "lobby"
    OPEN_OFFICE = "open_office"
    PRIVATE_OFFICE = "private_office"
    CONFERENCE = "conference"
    CORRIDOR = "corridor"
    KITCHEN_BREAK = "kitchen_break"
    MECHANICAL_ROOM = "mechanical_room"
    STORAGE = "storage"
    RETAIL_SALES = "retail_sales"

    # Education
    CLASSROOM = "classroom"
    LAB = "lab"

    # Healthcare
    PATIENT_ROOM = "patient_room"
    OPERATING_ROOM = "operating_room"

    # Industrial / warehouse
    WAREHOUSE_STORAGE = "warehouse_storage"
    LOADING_DOCK = "loading_dock"

    # Common / circulation
    COMMON_AREA = "common_area"
    STAIRWELL_ELEVATOR = "stairwell_elevator"
    PARKING = "parking"
    GARAGE = "garage"
    ENTRY = "entry"
    FOYER = "foyer"
    HALLWAY = "hallway"

    # Fallback
    OTHER = "other"


class Confidence(StrEnum):
    """Confidence level for extracted/assumed field values."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
