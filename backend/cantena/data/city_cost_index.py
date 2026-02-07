"""City cost indexes for location-based cost adjustment.

Indexes are relative to the national average (1.00).
Based on publicly available ENR and RSMeans city cost index data.
"""

from __future__ import annotations

# Maps (city_lower, state_lower) -> cost index.
# National average = 1.00.
CITY_COST_INDEXES: dict[tuple[str, str], float] = {
    # Northeast
    ("new york", "ny"): 1.30,
    ("boston", "ma"): 1.25,
    ("philadelphia", "pa"): 1.15,
    ("hartford", "ct"): 1.12,
    ("newark", "nj"): 1.18,
    ("providence", "ri"): 1.08,
    ("baltimore", "md"): 0.95,
    ("washington", "dc"): 1.05,
    ("pittsburgh", "pa"): 1.02,
    ("albany", "ny"): 1.05,
    # Southeast
    ("atlanta", "ga"): 0.92,
    ("miami", "fl"): 0.95,
    ("orlando", "fl"): 0.90,
    ("tampa", "fl"): 0.88,
    ("charlotte", "nc"): 0.88,
    ("raleigh", "nc"): 0.87,
    ("nashville", "tn"): 0.90,
    ("richmond", "va"): 0.92,
    # Midwest
    ("chicago", "il"): 1.12,
    ("detroit", "mi"): 1.02,
    ("minneapolis", "mn"): 1.08,
    ("cleveland", "oh"): 0.98,
    ("columbus", "oh"): 0.95,
    ("indianapolis", "in"): 0.95,
    ("milwaukee", "wi"): 1.02,
    ("kansas city", "mo"): 0.95,
    ("st. louis", "mo"): 1.00,
    # South / Southwest
    ("houston", "tx"): 0.88,
    ("dallas", "tx"): 0.90,
    ("san antonio", "tx"): 0.85,
    ("austin", "tx"): 0.88,
    ("new orleans", "la"): 0.88,
    ("oklahoma city", "ok"): 0.85,
    ("phoenix", "az"): 0.92,
    ("tucson", "az"): 0.88,
    # West
    ("san francisco", "ca"): 1.35,
    ("los angeles", "ca"): 1.20,
    ("san diego", "ca"): 1.12,
    ("sacramento", "ca"): 1.15,
    ("seattle", "wa"): 1.15,
    ("portland", "or"): 1.10,
    ("denver", "co"): 0.98,
    ("las vegas", "nv"): 1.02,
    ("salt lake city", "ut"): 0.92,
    ("honolulu", "hi"): 1.28,
    ("anchorage", "ak"): 1.25,
}

# State-level averages as fallback when city is not found.
STATE_COST_INDEXES: dict[str, float] = {
    "ny": 1.15,
    "ca": 1.20,
    "ma": 1.20,
    "ct": 1.10,
    "nj": 1.15,
    "pa": 1.05,
    "md": 0.95,
    "dc": 1.05,
    "il": 1.05,
    "wa": 1.10,
    "or": 1.05,
    "co": 0.98,
    "mn": 1.05,
    "hi": 1.25,
    "ak": 1.22,
    "tx": 0.88,
    "fl": 0.90,
    "ga": 0.92,
    "nc": 0.88,
    "tn": 0.90,
    "va": 0.92,
    "oh": 0.96,
    "mi": 1.00,
    "in": 0.95,
    "wi": 1.00,
    "mo": 0.97,
    "la": 0.88,
    "ok": 0.85,
    "az": 0.90,
    "nv": 1.00,
    "ut": 0.92,
    "ri": 1.05,
}

# Default index when neither city nor state is found
DEFAULT_COST_INDEX: float = 1.00
