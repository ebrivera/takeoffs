"""Standard CSI MasterFormat divisions with typical cost breakdowns.

Percentages represent typical distribution of costs by building type,
based on publicly available RSMeans data and industry standards.
"""

from __future__ import annotations

from dataclasses import dataclass

from cantena.models.enums import BuildingType


@dataclass(frozen=True)
class CSIDivision:
    """A CSI MasterFormat division with its number and name."""

    number: str
    name: str


# Standard CSI divisions relevant to building construction
CSI_DIVISIONS: list[CSIDivision] = [
    CSIDivision("01", "General Requirements"),
    CSIDivision("02", "Existing Conditions"),
    CSIDivision("03", "Concrete"),
    CSIDivision("04", "Masonry"),
    CSIDivision("05", "Metals"),
    CSIDivision("06", "Wood, Plastics & Composites"),
    CSIDivision("07", "Thermal & Moisture Protection"),
    CSIDivision("08", "Openings"),
    CSIDivision("09", "Finishes"),
    CSIDivision("10", "Specialties"),
    CSIDivision("11", "Equipment"),
    CSIDivision("12", "Furnishings"),
    CSIDivision("13", "Special Construction"),
    CSIDivision("14", "Conveying Equipment"),
    CSIDivision("21", "Fire Suppression"),
    CSIDivision("22", "Plumbing"),
    CSIDivision("23", "HVAC"),
    CSIDivision("25", "Integrated Automation"),
    CSIDivision("26", "Electrical"),
    CSIDivision("27", "Communications"),
    CSIDivision("28", "Electronic Safety & Security"),
    CSIDivision("31", "Earthwork"),
    CSIDivision("32", "Exterior Improvements"),
    CSIDivision("33", "Utilities"),
]


# Typical percentage breakdowns by building type.
# Each dict maps CSI division number -> percentage of total cost.
# Percentages are approximate and based on industry averages.
# Only divisions with meaningful cost contribution are included;
# remaining percentage is distributed to general requirements (01).

_RESIDENTIAL_BREAKDOWN: dict[str, float] = {
    "01": 5.0,
    "03": 6.0,
    "04": 5.0,
    "05": 4.0,
    "06": 10.0,
    "07": 6.0,
    "08": 5.5,
    "09": 14.0,
    "10": 1.0,
    "11": 1.5,
    "12": 1.0,
    "14": 2.0,
    "21": 2.5,
    "22": 6.0,
    "23": 10.0,
    "26": 9.0,
    "27": 1.0,
    "28": 0.5,
    "31": 3.0,
    "32": 4.0,
    "33": 3.0,
}

_OFFICE_BREAKDOWN: dict[str, float] = {
    "01": 5.0,
    "03": 7.0,
    "04": 3.0,
    "05": 8.0,
    "06": 4.0,
    "07": 5.0,
    "08": 7.0,
    "09": 12.0,
    "10": 1.5,
    "11": 1.0,
    "14": 3.0,
    "21": 2.5,
    "22": 4.5,
    "23": 12.0,
    "25": 1.5,
    "26": 10.0,
    "27": 2.0,
    "28": 1.0,
    "31": 3.0,
    "32": 4.0,
    "33": 3.0,
}

_RETAIL_BREAKDOWN: dict[str, float] = {
    "01": 5.5,
    "03": 6.0,
    "04": 5.0,
    "05": 7.0,
    "06": 5.0,
    "07": 6.5,
    "08": 8.0,
    "09": 13.0,
    "10": 2.0,
    "11": 2.0,
    "21": 2.0,
    "22": 4.0,
    "23": 10.0,
    "26": 10.0,
    "27": 1.5,
    "28": 1.0,
    "31": 3.5,
    "32": 5.0,
    "33": 3.0,
}

_WAREHOUSE_BREAKDOWN: dict[str, float] = {
    "01": 5.0,
    "03": 8.0,
    "05": 15.0,
    "06": 2.0,
    "07": 10.0,
    "08": 4.0,
    "09": 5.0,
    "10": 1.0,
    "11": 3.0,
    "21": 2.5,
    "22": 3.0,
    "23": 8.0,
    "26": 10.0,
    "27": 1.0,
    "28": 1.0,
    "31": 7.0,
    "32": 8.0,
    "33": 6.5,
}

_SCHOOL_BREAKDOWN: dict[str, float] = {
    "01": 5.0,
    "03": 6.0,
    "04": 6.0,
    "05": 5.0,
    "06": 5.0,
    "07": 5.5,
    "08": 6.0,
    "09": 13.0,
    "10": 2.0,
    "11": 3.0,
    "12": 2.0,
    "14": 1.0,
    "21": 2.5,
    "22": 5.0,
    "23": 11.0,
    "26": 9.5,
    "27": 1.5,
    "28": 1.0,
    "31": 3.5,
    "32": 4.0,
    "33": 2.5,
}

_HOSPITAL_BREAKDOWN: dict[str, float] = {
    "01": 4.0,
    "03": 6.0,
    "04": 2.0,
    "05": 5.0,
    "06": 3.0,
    "07": 4.0,
    "08": 5.0,
    "09": 10.0,
    "10": 2.0,
    "11": 5.0,
    "12": 2.0,
    "13": 1.0,
    "14": 2.5,
    "21": 3.0,
    "22": 6.0,
    "23": 14.0,
    "25": 2.0,
    "26": 10.0,
    "27": 2.5,
    "28": 2.0,
    "31": 3.0,
    "32": 3.5,
    "33": 2.5,
}

_HOTEL_BREAKDOWN: dict[str, float] = {
    "01": 5.0,
    "03": 6.0,
    "04": 4.0,
    "05": 5.0,
    "06": 6.0,
    "07": 5.5,
    "08": 5.5,
    "09": 14.0,
    "10": 2.0,
    "11": 2.0,
    "12": 3.0,
    "14": 2.5,
    "21": 2.5,
    "22": 5.5,
    "23": 11.0,
    "26": 9.0,
    "27": 1.5,
    "28": 1.0,
    "31": 3.0,
    "32": 3.5,
    "33": 2.5,
}


# Map building types to their typical CSI division breakdowns
DIVISION_BREAKDOWNS: dict[BuildingType, dict[str, float]] = {
    BuildingType.APARTMENT_LOW_RISE: _RESIDENTIAL_BREAKDOWN,
    BuildingType.APARTMENT_MID_RISE: _RESIDENTIAL_BREAKDOWN,
    BuildingType.APARTMENT_HIGH_RISE: _RESIDENTIAL_BREAKDOWN,
    BuildingType.OFFICE_LOW_RISE: _OFFICE_BREAKDOWN,
    BuildingType.OFFICE_MID_RISE: _OFFICE_BREAKDOWN,
    BuildingType.OFFICE_HIGH_RISE: _OFFICE_BREAKDOWN,
    BuildingType.RETAIL: _RETAIL_BREAKDOWN,
    BuildingType.WAREHOUSE: _WAREHOUSE_BREAKDOWN,
    BuildingType.SCHOOL_ELEMENTARY: _SCHOOL_BREAKDOWN,
    BuildingType.SCHOOL_HIGH: _SCHOOL_BREAKDOWN,
    BuildingType.HOSPITAL: _HOSPITAL_BREAKDOWN,
    BuildingType.HOTEL: _HOTEL_BREAKDOWN,
}
