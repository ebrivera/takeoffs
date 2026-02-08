# Cantena Cost Engine — PRD (Foundation)

## Project metadata

- **Project:** cantena-cost-engine
- **Branch:** ralph/cost-engine-foundation
- **Description:**  
  The cost estimation engine for Cantena — a standalone, well-tested Python library that takes a BuildingModel (describing a building's type, size, structural system, etc.) and produces a CostEstimate (budget broken down by CSI division with confidence ranges). This is the domain core that the VLM pipeline and web UI will later depend on. No UI, no VLM, no PDF processing — just the estimation logic, cost data, and domain types. This PRD is the predecessor to the full product PRD. Everything here must be solid because it's the foundation the rest of the system builds on.

---

## Quality gates

Run these to validate PRD completion:

1. `cd backend && python -m pytest tests/ -v --tb=short`
2. `cd backend && python -m pytest tests/ --cov=cantena --cov-report=term-missing --cov-fail-under=85`
3. `cd backend && python -m mypy cantena/ --strict`
4. `cd backend && python -m ruff check cantena/ tests/`

---

## User stories

### US-001 — Project scaffolding and tooling

- **Category:** setup
- **Title:** Project scaffolding and tooling
- **Description:**  
  As a developer, I want a properly structured Python project with linting, type checking, and testing configured so that every subsequent story has a quality foundation to build on.

#### Acceptance criteria

- Directory structure: `backend/cantena/` (source), `backend/tests/` (tests), `backend/pyproject.toml`
- `pyproject.toml` configures: pytest, mypy (strict mode), ruff, pytest-cov
- Dependencies installed: pytest, pytest-cov, mypy, ruff, pydantic (for domain models)
- `cantena/` has `__init__.py`, `py.typed` marker file
- A trivial test in `tests/test_smoke.py` that imports `cantena` and passes
- All quality gates pass: pytest, mypy --strict, ruff check
- A `README.md` in `backend/` explaining the project structure and how to run tests

- **Passes:** false
- **Notes:**  
  Use Python 3.11+. Use pydantic v2 for domain models — it gives us runtime validation, JSON serialization, and schema generation for free. Do NOT add FastAPI or any web framework yet — this PRD is library-only. Keep dependencies minimal.

---

### US-002 — Domain models: BuildingModel and related types

- **Category:** core
- **Title:** Domain models: BuildingModel and related types
- **Description:**  
  As a developer, I want well-typed domain models that represent the input to the cost engine (what the VLM will eventually extract from drawings) so that the rest of the system has a clear, validated contract to work with.

#### Acceptance criteria

- `cantena/models/building.py` defines `BuildingModel` as a Pydantic `BaseModel` with fields:
  - `building_type` (enum)
  - `building_use` (str)
  - `gross_sf` (float)
  - `stories` (int)
  - `story_height_ft` (float)
  - `structural_system` (enum)
  - `exterior_wall_system` (enum)
  - `mechanical_system` (enum or None)
  - `electrical_service` (enum or None)
  - `fire_protection` (enum or None)
  - `location` (Location model with city, state, zip_code)
  - `complexity_scores` (ComplexityScores model with structural, mep, site, finish fields each 1-5 int)
  - `special_conditions` (list[str], default empty)
  - `confidence` (dict mapping field names to Confidence enum HIGH/MEDIUM/LOW)
- Enums defined in `cantena/models/enums.py`:
  - `BuildingType` (at least: OFFICE, APARTMENT_LOW_RISE, APARTMENT_MID_RISE, APARTMENT_HIGH_RISE, SCHOOL, HOSPITAL, WAREHOUSE, RETAIL, RESTAURANT, CHURCH, PARKING_GARAGE, DORMITORY)
  - `StructuralSystem` (STEEL_FRAME, CONCRETE_FRAME, WOOD_FRAME, MASONRY_BEARING, PRECAST_CONCRETE)
  - `ExteriorWall` (BRICK_VENEER, CURTAIN_WALL, METAL_PANEL, PRECAST_PANEL, STUCCO_ON_FRAME, WOOD_SIDING, EIFS)
  - `MechanicalSystem` (STANDARD_HVAC, VRF, CHILLED_WATER, RADIANT, GEOTHERMAL)
  - `ElectricalService` (STANDARD_120_208V, STANDARD_277_480V, HIGH_POWER)
  - `FireProtection` (WET_SPRINKLER, DRY_SPRINKLER, NONE)
  - `Confidence` (HIGH, MEDIUM, LOW)
- `Location` model in `cantena/models/building.py` with:
  - `city` (str)
  - `state` (str)
  - `zip_code` (str, optional)
- `ComplexityScores` model with validation that each score is 1-5
- All models export cleanly from `cantena.models`
- Tests in `tests/test_models.py`:
  - valid construction
  - validation errors for bad data (negative SF, stories < 1, complexity out of range)
  - JSON round-trip serialization
  - default values work correctly
- `mypy --strict` passes on all model files

- **Passes:** false
- **Notes:**  
  These enums and models represent the RSMeans square foot estimator input parameters mapped to our domain. BuildingType values come from RSMeans' 100+ building type models — we start with the most common 12. The confidence dict is important: it lets the VLM signal which fields it's sure about vs guessing. Keep models in a models/ subpackage for organization.

---

### US-003 — Domain models: CostEstimate and budget output types

- **Category:** core
- **Title:** Domain models: CostEstimate and budget output types
- **Description:**  
  As a developer, I want well-typed output models that represent a conceptual cost estimate so that consumers (UI, PDF export, API) have a clear, structured contract.

#### Acceptance criteria

- `cantena/models/estimate.py` defines `CostEstimate` as a Pydantic `BaseModel` with fields:
  - `project_name` (str)
  - `building_summary` (BuildingSummary — subset of BuildingModel for display)
  - `total_cost` (CostRange model with low, expected, high floats)
  - `cost_per_sf` (CostRange)
  - `breakdown` (list[DivisionCost])
  - `assumptions` (list[Assumption])
  - `generated_at` (datetime)
  - `location_factor` (float)
  - `metadata` (EstimateMetadata)
- `DivisionCost` model:
  - `csi_division` (str like '03')
  - `division_name` (str like 'Concrete')
  - `cost` (CostRange)
  - `percent_of_total` (float)
  - `source` (str describing where cost came from)
- `CostRange` model:
  - `low` (float)
  - `expected` (float)
  - `high` (float)
  - with validator that `low <= expected <= high`
- `Assumption` model:
  - `parameter` (str)
  - `assumed_value` (str)
  - `reasoning` (str)
  - `confidence` (Confidence enum)
- `BuildingSummary` model:
  - `building_type` (str)
  - `gross_sf` (float)
  - `stories` (int)
  - `structural_system` (str)
  - `exterior_wall` (str)
  - `location` (str)
- `EstimateMetadata` model:
  - `engine_version` (str)
  - `cost_data_version` (str)
  - `estimation_method` (str, default 'square_foot_conceptual')
- Tests in `tests/test_models_estimate.py`:
  - valid construction
  - CostRange validation
  - JSON serialization
  - a helper that builds a realistic example estimate for use in other tests
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  CostRange is a key concept — we NEVER output a single number. Every cost is low/expected/high. This is both methodologically correct (RSMeans ROM estimates are ±25%) and builds trust with PMs (Gunnar's insight). The Assumption model makes the AI's reasoning transparent — every number traces back to a source.

---

### US-004 — Cost data layer: schema and seed data for building types

- **Category:** core
- **Title:** Cost data layer: schema and seed data for building types
- **Description:**  
  As a developer, I want a cost data layer with seed data for common building types so that the cost engine can look up square-foot costs by building type, structural system, and wall system.

#### Acceptance criteria

- `cantena/data/` directory with cost data stored as structured Python dataclasses or Pydantic models (NOT a database yet — in-memory for now, easy to move to DB later)
- `cantena/data/building_costs.py` defines `SquareFootCostEntry`:
  - `building_type` (BuildingType)
  - `structural_system` (StructuralSystem)
  - `exterior_wall` (ExteriorWall)
  - `stories_range` (tuple[int, int] — min/max stories this applies to)
  - `cost_per_sf` (CostRange with low/expected/high)
  - `year` (int, e.g. 2025)
  - `notes` (str)
- `cantena/data/seed.py` contains at least 15 `SquareFootCostEntry` records covering realistic combinations:
  - 3-story wood-frame apartment with brick veneer
  - 5-story concrete apartment with EIFS
  - 3-story steel office with curtain wall
  - 1-story steel warehouse with metal panel
  - 2-story masonry school with brick
  - 1-story wood retail with stucco
  - etc.  
    Costs should be realistic 2025 national averages (e.g., wood-frame apartment ~$180-250/SF, steel office ~$200-350/SF, warehouse ~$100-150/SF)
- `cantena/data/csi_divisions.py` defines the standard CSI divisions (01 General Requirements through 49 — at least divisions 01-14, 21-28, 31-33) with typical percentage breakdowns by building type.  
  E.g., for an office:
  - Div 03 Concrete ~8%
  - Div 05 Metals ~12%
  - Div 07 Thermal/Moisture ~6%
  - Div 09 Finishes ~10%
  - Div 23 HVAC ~15%
  - etc.
- `cantena/data/city_cost_index.py` with at least 30 city cost indexes:
  - New York (1.30)
  - San Francisco (1.35)
  - Los Angeles (1.15)
  - Chicago (1.10)
  - Houston (0.88)
  - Atlanta (0.92)
  - Baltimore (0.95)
  - Boston (1.20)
  - Denver (0.98)
  - Phoenix (0.90)
  - Seattle (1.12)
  - etc.  
    National average = 1.00
- `cantena/data/repository.py` defines `CostDataRepository` class with methods:
  - `get_sf_cost(building_type, structural_system, exterior_wall, stories) -> SquareFootCostEntry | None`
  - `get_best_match_sf_cost(building_type, structural_system, exterior_wall, stories) -> SquareFootCostEntry` (fuzzy match with fallbacks)
  - `get_division_breakdown(building_type) -> list[DivisionPercentage]`
  - `get_city_cost_index(city, state) -> float` (returns 1.0 if not found)
- Tests in `tests/test_cost_data.py`:
  - exact match lookup works
  - fuzzy match falls back sensibly (e.g., wrong wall type still returns a cost for that building type)
  - city index lookup works for known and unknown cities
  - division percentages sum to approximately 100%
  - seed data has no duplicate entries
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  We're using in-memory data intentionally. PostgreSQL comes later when we need persistence, user-specific overrides, and historical project data. The CostDataRepository abstraction means we can swap the backend without changing the engine. The fuzzy matching in `get_best_match_sf_cost` is critical — the VLM might extract a building type + system combination we don't have an exact match for, and we need a reasonable fallback rather than an error. Cost data comes from publicly available RSMeans square foot cost book data and ENR construction cost indexes.

---

### US-005 — Cost engine: BuildingModel → CostEstimate

- **Category:** core
- **Title:** Cost engine: BuildingModel → CostEstimate
- **Description:**  
  As a developer, I want the core estimation engine that takes a BuildingModel and produces a CostEstimate so that I have the complete domain logic working end-to-end before adding any VLM or UI layer.

#### Acceptance criteria

- `cantena/engine.py` defines `CostEngine` class that takes a `CostDataRepository` in its constructor
- `CostEngine.estimate(building: BuildingModel, project_name: str = 'Untitled') -> CostEstimate` method implements the full estimation pipeline
- Pipeline steps:
  1. Look up base $/SF cost from repository using building type + structural system + exterior wall + stories
  2. Apply location factor from city cost index
  3. Apply complexity multipliers — each complexity score maps to a multiplier:
     - 1 = 0.85
     - 2 = 0.95
     - 3 = 1.00
     - 4 = 1.10
     - 5 = 1.25  
       Composite multiplier is weighted average
  4. Calculate total cost = gross_sf \* adjusted_cost_per_sf
  5. Generate CostRange for total (low = expected _ 0.80, high = expected _ 1.25 for conceptual estimates)
  6. Break down total into CSI divisions using percentage lookup
  7. Collect assumptions from confidence dict and any fallback decisions made during lookup
- Each assumption is documented:
  - if fuzzy match was used, assumption says "Closest match used: X instead of Y"
  - if confidence is LOW on a field, assumption says "Low confidence on X — estimate may vary significantly"
- If no cost data match found at all, raises a descriptive `ValueError` (not a silent fallback to garbage)
- Tests in `tests/test_engine.py`:
  1. Simple happy path — wood-frame apartment in Baltimore produces reasonable estimate ($180-250/SF range)
  2. Location factor applies correctly — same building in NYC vs Houston shows ~40% cost difference
  3. Complexity multipliers work — high complexity (all 5s) produces ~25% higher estimate than standard (all 3s)
  4. Division breakdown sums to total
  5. Assumptions list is populated when fuzzy matching occurs
  6. ValueError raised for completely unknown building type
  7. Low confidence fields produce explicit assumptions in output
- Tests use realistic construction values — a 45,000 SF office building should estimate somewhere in the $9M-$16M range depending on location and quality
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This is THE core story. The complexity multiplier approach is how experienced estimators adjust conceptual estimates — they don't recalculate from scratch, they apply judgment-based multipliers to a baseline. The 0.80-1.25 range for CostRange matches RSMeans' ±20-25% accuracy for square foot estimates. The weighted average for complexity:
  - structural gets 0.3 weight
  - MEP gets 0.3
  - finishes gets 0.25
  - site gets 0.15  
    These reflect typical cost distribution in commercial construction.

---

### US-006 — Convenience factory and public API surface

- **Category:** integration
- **Title:** Convenience factory and public API surface
- **Description:**  
  As a developer integrating the cost engine (from a FastAPI route, a CLI, or a test), I want a simple, well-documented API surface so that I don't need to understand the internal wiring to use it.

#### Acceptance criteria

- `cantena/__init__.py` exports:
  - `CostEngine`
  - `BuildingModel`
  - `CostEstimate`
  - `CostRange`
  - `create_default_engine` (factory function)
  - and all enum types
- `cantena/factory.py` defines `create_default_engine() -> CostEngine` that wires up `CostDataRepository` with seed data — one line to get a working engine
- Usage is simple:
  - `from cantena import create_default_engine, BuildingModel`
  - `engine = create_default_engine()`
  - `estimate = engine.estimate(building)`
- `cantena/engine.py` has a module-level docstring explaining the estimation methodology (square foot conceptual estimating, what it is, what accuracy to expect)
- `CostEngine.estimate()` has a complete docstring with Args, Returns, Raises, and Example sections
- Tests in `tests/test_public_api.py`:
  1. Import and use via the public API surface only
  2. `create_default_engine` works
  3. Full round-trip: construct BuildingModel -> estimate -> serialize to JSON -> deserialize back
  4. The JSON output is a valid structure that a frontend could consume
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This is about developer ergonomics. When PRD 2 adds FastAPI and the VLM pipeline, the integration point should be dead simple. The JSON round-trip test is important because the frontend will consume this over HTTP.

---

### US-007 — End-to-end scenario tests with realistic buildings

- **Category:** integration
- **Title:** End-to-end scenario tests with realistic buildings
- **Description:**  
  As a developer, I want end-to-end scenario tests with realistic construction projects so that I have confidence the engine produces sensible estimates before connecting it to a VLM or UI.

#### Acceptance criteria

- `tests/test_scenarios.py` contains at least 4 realistic scenario tests, each building a complete BuildingModel and asserting the estimate is in a reasonable range
- Scenario 1 - Suburban Apartment:
  - 3-story wood-frame
  - 36,000 SF
  - brick veneer
  - Baltimore MD
  - standard complexity  
    Assert total between $5.5M-$10M, cost/SF between $150-$280
- Scenario 2 - Urban Office:
  - 8-story steel frame
  - 120,000 SF
  - curtain wall
  - New York NY
  - high complexity (4,4,3,4)  
    Assert total between $30M-$55M, cost/SF between $250-$450
- Scenario 3 - Distribution Warehouse:
  - 1-story steel frame
  - 80,000 SF
  - metal panel
  - Houston TX
  - low complexity (2,2,1,2)  
    Assert total between $6M-$14M, cost/SF between $75-$175
- Scenario 4 - Elementary School:
  - 2-story masonry
  - 45,000 SF
  - brick veneer
  - Denver CO
  - standard complexity  
    Assert total between $9M-$18M, cost/SF between $200-$400
- Each scenario asserts:
  - (a) estimate is not None
  - (b) total cost range is populated
  - (c) cost per SF is in expected range for this building type
  - (d) at least 5 CSI divisions in breakdown
  - (e) division costs sum to approximately the total
  - (f) assumptions list is not empty
  - (g) location factor was applied (check metadata or compare to national average)
- A helper function or fixture provides each scenario as a BuildingModel for reuse in future tests
- All quality gates pass

- **Passes:** false
- **Notes:**  
  These ranges are intentionally wide because conceptual estimates ARE wide. The point isn't exact accuracy — it's that we don't produce obviously wrong numbers. A 36K SF apartment building shouldn't estimate at $500K (too low) or $50M (too high). These scenarios will also serve as integration test data when we add the VLM — we can compare VLM-extracted parameters against these known models. The cost ranges come from RSMeans 2025 data and real project experience.

---

### US-008 — JSON output formatting and estimate summary helpers

- **Category:** polish
- **Title:** JSON output formatting and estimate summary helpers
- **Description:**  
  As a developer building the future frontend, I want helper methods that produce well-formatted summary data from a CostEstimate so that I don't have to reimplement formatting logic in the UI layer.

#### Acceptance criteria

- `cantena/formatting.py` defines `format_currency(amount: float) -> str` that formats as `'$X,XXX,XXX'` (no cents for estimates over $10K, with cents for smaller amounts)
- `cantena/formatting.py` defines `format_cost_range(cr: CostRange) -> str` that produces `'$X.XM - $X.XM'` for millions, `'$XXX,XXX - $XXX,XXX'` for smaller amounts
- `cantena/formatting.py` defines `format_sf_cost(cr: CostRange) -> str` that produces `'$XXX - $XXX / SF'`
- `CostEstimate` gets a method `to_summary_dict() -> dict` that returns a flat, frontend-friendly dictionary with:
  - project_name
  - building_type
  - gross_sf_formatted (with commas)
  - total_cost_formatted (the expected value)
  - total_cost_range_formatted
  - cost_per_sf_formatted
  - cost_per_sf_range_formatted
  - location
  - location_factor
  - num_divisions
  - top_cost_drivers (top 3 divisions by cost, as list of {name, cost_formatted, percent})
  - num_assumptions
  - generated_at_formatted
- `CostEstimate` gets a method `to_export_dict() -> dict` that returns the full detailed data suitable for Excel or PDF export:
  - all division costs with formatted values
  - all assumptions
  - all metadata
- Tests in `tests/test_formatting.py`:
  - currency formatting edge cases (0, small amounts, millions, billions)
  - cost range formatting
  - summary dict has all expected keys
  - export dict has all expected keys
  - formatting is consistent (no mixing of $1.2M and $1,200,000 in the same output)
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  Construction PMs care deeply about how numbers are presented. '$12.4M' is how they talk about project costs, not '$12,437,892.34'. The summary dict is designed to be directly consumable by a React frontend — no further transformation needed. The export dict will feed into PDF and Excel generation in PRD 2.
