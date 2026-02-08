# Cantena Enhanced Cost Intelligence — PRD

## Project metadata

- **Project:** cantena-enhanced-cost-intelligence
- **Branch:** ralph/enhanced-cost-intelligence
- **Description:**  
  Upgrades the cost engine from a building-type-level lookup table to an assembly-level estimation system that uses room-type awareness and geometry-detected room polygons to produce more granular and accurate conceptual estimates.

  PRD 3.75 gave us individually measured room polygons with labels (`DetectedRoom` via Shapely `polygonize`) and LLM-assisted semantic interpretation (`LlmGeometryInterpreter`). This PRD prices each detected room at its room-type-specific rate, producing estimates like:
  - `LIVING ROOM: 180 SF @ $220/SF`
  - `KITCHEN: 160 SF @ $280/SF`
  - `UTILITY: 40 SF @ $150/SF`  
    instead of a single building-level calculation like:
  - `512 SF @ $200/SF = $102K`

  **Depends on:** PRD 1 (cost engine), PRD 2 (product pipeline), PRD 3 (geometry engine), PRD 3.75 (room detection + LLM interpretation).

---

## Quality gates

1. `cd backend && python -m pytest tests/ -v --tb=short -k 'not llm'`
2. `cd backend && python -m pytest tests/ --cov=cantena --cov-report=term-missing --cov-fail-under=80`
3. `cd backend && python -m mypy cantena/ --strict`
4. `cd backend && python -m ruff check cantena/ tests/`

---

## User stories

### US-401 — Room-type cost differentiation data

- **Category:** core
- **Title:** Room-type cost differentiation data
- **Description:**  
  As a developer, I want cost data that differentiates between room types within a building (lobby vs. open office vs. kitchen vs. bathroom vs. corridor) so that the estimate reflects actual cost variation across different spaces rather than applying a single $/SF rate to the whole building.

#### Acceptance criteria

- `cantena/data/room_costs.py` defines `RoomTypeCost` model:
  - `room_type` (`RoomType` enum)
  - `building_context` (`BuildingType`)
  - `base_cost_per_sf` (`CostRange`)
  - `typical_percent_of_building` (float — percent of typical building of this type)
  - `cost_drivers` (list[str] — why expensive/cheap)
  - `notes` (str)
- `RoomType` enum added to `cantena/models/enums.py`:
  - `LIVING_ROOM, KITCHEN, DINING, BEDROOM, BATHROOM, RESTROOM, WC, UTILITY, LAUNDRY, CLOSET, PORCH, LOBBY, OPEN_OFFICE, PRIVATE_OFFICE, CONFERENCE, CORRIDOR, KITCHEN_BREAK, MECHANICAL_ROOM, STORAGE, RETAIL_SALES, CLASSROOM, LAB, PATIENT_ROOM, OPERATING_ROOM, WAREHOUSE_STORAGE, LOADING_DOCK, COMMON_AREA, STAIRWELL_ELEVATOR, PARKING, GARAGE, ENTRY, FOYER, HALLWAY, OTHER`
  - enum includes both residential and commercial room types (geometry engine can detect rooms on any drawing)
- Seed data covers at least:
  - **Residential**
    - living room: **$180–250/SF**
    - kitchen: **$250–350/SF**
    - bathroom: **$300–450/SF**
    - bedroom: **$150–220/SF**
    - dining: **$170–240/SF**
    - utility: **$100–160/SF**
    - laundry: **$120–180/SF**
    - porch: **$80–130/SF**
    - garage: **$60–100/SF**
    - closet: **$100–150/SF**
  - **Office**
    - lobby: **$300–400/SF**
    - open office: **$200–280/SF**
    - corridor: **$150–200/SF**
    - restroom: **$350–500/SF**
    - conference: **$250–350/SF**
    - mechanical: **$120–180/SF**
  - **School**
    - classroom: **$250–350/SF**
    - corridor: **$180–220/SF**
  - **Hospital**
    - patient room: **$400–600/SF**
    - operating room: **$800–1200/SF**
- `CostDataRepository` extended:
  - `get_room_type_costs(building_type: BuildingType) -> list[RoomTypeCost]`
  - residential building types return residential room costs; commercial returns commercial
  - fallback: if room type not found for building context, use `OTHER` at generic rate
- Tests in `tests/test_room_costs.py`:
  1. office building has at least 5 room types
  2. residential has at least 6 room types (living, kitchen, bedroom, bathroom, utility, dining)
  3. cost ranges make sense (kitchen > utility)
  4. typical percentages roughly sum to 90–110%
  5. all room types have non-empty cost drivers
  6. unknown room type falls back to `OTHER`
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  Key change from original PRD 4: RoomType now includes residential room types because PRD 3.75 detects these from real drawings (e.g., `first-floor.pdf` farmhouse). The cost data must price these. Kitchens cost more than bedrooms due to cabinets/counters/plumbing/appliances; bathrooms due to fixtures/tile/plumbing density.

---

### US-402 — Space program model with DetectedRoom bridge

- **Category:** core
- **Title:** Space program model with DetectedRoom bridge
- **Description:**  
  As a developer, I want a `SpaceProgram` model that can be populated from three sources — (1) PRD 3.75 DetectedRoom polygons (highest accuracy), (2) LLM interpretation room breakdown, or (3) default distribution from BuildingModel — so that the cost engine always has a room-by-room program to price, regardless of how much geometry data is available.

#### Acceptance criteria

- `cantena/models/space_program.py` defines `SpaceProgram` as a Pydantic model with:
  - `spaces: list[Space]`
  - `building_type: BuildingType`
  - `total_area_sf` computed property summing all spaces
- `Space` model:
  - `room_type: RoomType`
  - `name: str` (e.g., "Living Room")
  - `area_sf: float`
  - `count: int = 1` (for repeated rooms like patient rooms)
  - `source: SpaceSource` enum (`GEOMETRY | LLM | ASSUMED`)
  - `confidence: Confidence`
- `SpaceProgram.from_detected_rooms(rooms: list[DetectedRoom], building_type: BuildingType) -> SpaceProgram`
  - maps `DetectedRoom.label` to `RoomType` via `LABEL_TO_ROOM_TYPE` dict:
    - `"LIVING ROOM" -> LIVING_ROOM`
    - `"KITCHEN" -> KITCHEN`
    - `"WC" -> WC`
    - `"UTILITY" -> UTILITY`
    - `"DINING" -> DINING`
    - `"LAUNDRY" -> LAUNDRY`
    - `"COATS" -> CLOSET`
    - `"FRONT PORCH" -> PORCH`
    - `"BACK PORCH" -> PORCH`
    - etc.
  - rooms without labels or unmapped labels => `RoomType.OTHER`
  - `source=GEOMETRY` for all
  - uses `DetectedRoom.area_sf`
- `SpaceProgram.from_llm_interpretation(interp: LlmInterpretation, total_area_sf: float, building_type: BuildingType) -> SpaceProgram`
  - maps `LlmRoomInterpretation.room_type_enum` to `RoomType`
  - `source=LLM` for all
- `SpaceProgram.from_building_model(model: BuildingModel) -> SpaceProgram`
  - distributes gross SF across room types using `typical_percent_of_building`
  - `source=ASSUMED` for all
- `SpaceProgram.update_space(index: int, area_sf: float | None = None, room_type: RoomType | None = None, name: str | None = None)`
  - user override behavior: changes source to `USER_OVERRIDE` on the affected `Space`
- Priority: `from_detected_rooms` > `from_llm_interpretation` > `from_building_model`
- Tests in `tests/test_space_program.py`:
  1. `from_detected_rooms` with 3 labeled rooms produces 3 Spaces with GEOMETRY source
  2. maps `"LIVING ROOM" -> LIVING_ROOM`, `"WC" -> WC`, `"COATS" -> CLOSET`
  3. `from_building_model` generates reasonable residential distribution (~30% living, ~15% kitchen, ~15% bedrooms, ~10% bathroom, ~10% utility, ~10% circulation, ~10% other)
  4. `from_llm_interpretation` maps LLM room types correctly
  5. `total_area_sf` sums correctly
  6. `update_space` changes source to USER_OVERRIDE
  7. unlabeled `DetectedRoom` maps to `OTHER`
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This is the bridge between PRD 3.75 (`DetectedRoom` polygons) and room pricing. The mapping handles label variance (e.g., "WC" vs "BATHROOM", "COATS" as closet). `SpaceSource` has four values: `GEOMETRY, LLM, ASSUMED, USER_OVERRIDE`.

---

### US-403 — Room-type-aware cost engine

- **Category:** core
- **Title:** Room-type-aware cost engine
- **Description:**  
  As a developer, I want the `CostEngine` to optionally accept a `SpaceProgram` and price each room type separately so estimates reflect cost variation across spaces.

#### Acceptance criteria

- `CostEngine.estimate` accepts optional `space_program: SpaceProgram | None`
- When `space_program` is provided:
  1. Each `Space` priced using its room-type-specific $/SF from `RoomTypeCost` data via `get_room_type_costs(building_type)` + room_type match
  2. Location factor and complexity multipliers still apply per-room
  3. Total cost is sum of room costs (not one gross_sf calc)
  4. CSI division breakdown computed by weighted average of room-type breakdowns
  5. If a room type has no specific cost data (`OTHER` / unmapped), fall back to whole-building $/SF for that room
- When `space_program` is None: existing whole-building behavior preserved
- `CostEstimate` extended:
  - `space_breakdown: list[SpaceCost] | None`
  - `SpaceCost` fields:
    - `room_type: str`
    - `name: str`
    - `area_sf: float`
    - `cost_per_sf: CostRange`
    - `total_cost: CostRange`
    - `percent_of_total: float`
    - `source: str` ("geometry" | "llm" | "assumed" | "user_override")
- Tests in `tests/test_engine_rooms.py`:
  1. residential SpaceProgram: kitchen priced higher per SF than utility
  2. office: lobby most expensive per SF vs open office/corridor
  3. sum of space_breakdown costs matches total_cost within 1%
  4. without SpaceProgram, existing behavior unchanged
  5. `RoomType.OTHER` falls back to whole-building rate
  6. `SpaceCost.source` populated correctly from Space.source
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  SpaceCost includes a source field so frontend can show where each room came from. Unmapped rooms must not break pricing.

---

### US-404 — SpaceProgram assembly: merge geometry rooms with LLM enrichment

- **Category:** core
- **Title:** SpaceProgram assembly: merge geometry rooms with LLM enrichment
- **Description:**  
  As a developer, I want a service that assembles the best possible SpaceProgram by merging geometry-detected rooms with LLM interpretation, filling gaps and resolving conflicts.

#### Acceptance criteria

- `cantena/services/space_assembler.py` defines `SpaceAssembler`
- `SpaceAssembler.assemble(page_measurements: PageMeasurements, building_model: BuildingModel) -> SpaceProgram` uses priority:
  1. if `page_measurements.rooms` exists and has labeled rooms: `SpaceProgram.from_detected_rooms()`
  2. else if `page_measurements.llm_interpretation` has room data: `SpaceProgram.from_llm_interpretation()`
  3. else fallback: `SpaceProgram.from_building_model()`
- When using `from_detected_rooms`, also consult `llm_interpretation` to:
  - re-classify unlabeled rooms (size/position suggestions)
  - add missing rooms (LLM-only spaces if geometry missed them)
  - flag anomalies (e.g., WC far too large)
- `SpaceAssembler.reconcile_areas(program: SpaceProgram, expected_total_sf: float) -> SpaceProgram`:
  - if detected room sum differs from expected total, add an `Unaccounted` Space of type `OTHER` for the gap
  - rooms are not scaled; measurements are trusted, gap is explicit
- Tests in `tests/test_space_assembler.py`:
  1. geometry rooms available → uses from_detected_rooms
  2. no geometry but LLM available → uses from_llm_interpretation
  3. neither available → uses from_building_model
  4. unlabeled geometry rooms get LLM-suggested labels
  5. area gap creates Unaccounted space
  6. anomaly flagging: oversized WC noted
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This is the assembly layer: geometry-first, LLM fills gaps/flags issues, assumed distribution is last resort. The area-gap policy avoids silently “making the numbers match.”

---

### US-405 — Full enhanced pipeline: geometry rooms + LLM enrichment + room-type costing

- **Category:** integration
- **Title:** Full enhanced pipeline: geometry rooms + LLM enrichment + room-type costing
- **Description:**  
  As a developer, I want the full pipeline to chain geometry room detection → LLM interpretation → SpaceProgram assembly → room-type-aware cost engine so that `/api/analyze` produces per-room estimates from actual drawing measurements.

#### Acceptance criteria

- `AnalysisPipeline` updated to use enhanced flow when PRD 3.75 components are available
- Enhanced flow:
  1. process PDF to images (existing)
  2. extract geometry: vectors → scale → walls → room polygons via polygonize → label rooms from text blocks (PRD 3 + 3.75)
  3. run LLM interpretation on geometry summary (PRD 3.75 `LlmGeometryInterpreter`, if API key available)
  4. assemble SpaceProgram (US-404 `SpaceAssembler`)
  5. run CostEngine with SpaceProgram (US-403)
  6. return enhanced PipelineResult
- `PipelineResult` extended:
  - `space_program: SpaceProgram | None`
  - `space_breakdown: list[SpaceCost] | None`
  - `room_detection_method: str` ("polygonize" | "llm_only" | "assumed" | None)
- `/api/analyze` response includes `space_breakdown` when available (name, type, area, cost/SF, total cost, percent, source)
- Backward compatible:
  - scanned PDF/no geometry → VLM-only analysis + assumed SpaceProgram from BuildingModel
  - geometry but no LLM key → geometry rooms + label matching only
  - full system → geometry rooms + LLM enrichment + room-type costing
- Tests in `tests/test_enhanced_pipeline.py`:
  1. enhanced flow (with mocks) returns SpaceProgram with `room_detection_method="polygonize"`
  2. fallback without geometry returns `room_detection_method="assumed"`
  3. API response includes `space_breakdown`
  4. space costs sum to total_cost
  5. backward compatible pipeline without SpaceAssembler still works
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  Geometry finds rooms; AI adds semantics; pricing uses room types. `room_detection_method` communicates trust level to the user/UI.

---

### US-406 — Frontend: space breakdown display and room-level override

- **Category:** polish
- **Title:** Frontend: space breakdown display and room-level override
- **Description:**  
  As a PM reviewing an estimate, I want to see cost broken down by room type with clear source indicators and be able to adjust room areas so I can validate the identified spaces quickly.

#### Acceptance criteria

- Results UI updated: new “Space Program” section between building parameters and CSI division breakdown
- Space Program section table:
  - room name, room type, area (SF), cost/SF (range), total cost, percent of total
  - sorted by cost descending
- Source indicators per row:
  - tape-measure icon for GEOMETRY
  - brain icon for LLM
  - dashed-circle icon for ASSUMED
  - pencil icon for USER_OVERRIDE  
    Tooltip explains source (“Measured from drawing geometry”, “Identified by AI analysis”, etc.)
- Room area editable (number input); room type changeable via dropdown from RoomType enum
- Users can add/remove rooms; editing changes source to USER_OVERRIDE
- “Recalculate” button sends updated SpaceProgram + BuildingModel to `POST /api/estimate` and refreshes
- `POST /api/estimate` accepts optional `space_program: SpaceProgram` JSON; when provided, CostEngine uses room-type-aware pricing
- If no rooms detected (`space_breakdown` null), Space Program section shows fallback message + assumed distribution table
- `npm run typecheck` and `npm run lint` pass
- Backend tests: `/api/estimate` with SpaceProgram body returns room-type-aware estimate with `space_breakdown`

- **Passes:** false
- **Notes:**  
  The key UX trust signal is the GEOMETRY (“tape-measure”) indicator: it means measured from the drawing, not guessed. The “no rooms detected” fallback ensures the UI never looks broken.
