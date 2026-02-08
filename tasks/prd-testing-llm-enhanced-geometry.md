# Cantena Geometry LLM Enhanced — PRD

## Project metadata

- **Project:** cantena-geometry-llm-enhanced
- **Branch:** ralph/geometry-llm-enhanced
- **Description:**  
  Enhances the geometry engine with three accuracy improvements:
  1. Replace convex hull area computation with Shapely `polygonize()`-based room polygon reconstruction — instead of wrapping all walls in a convex hull (which overestimates by including porches and dead space), feed wall segments as LineStrings into `shapely.polygonize()` to recover actual enclosed room polygons, then sum their areas.
  2. Add endpoint snapping to close near-miss gaps in wall segments before polygonization — CAD exports often have sub-point gaps that prevent polygon closure.
  3. Add LLM-assisted analysis using real :contentReference[oaicite:0]{index=0} API calls to interpret extracted geometry + text data, identify rooms semantically, validate measurements, and produce a richer SpaceProgram.

  **Scale safety rail (added):** scale detection is a linchpin (scale² impact on area). Add an LLM-backed _verification / fallback_ path that can confirm the parsed scale from title block text (or a cropped title-block image) and prevent catastrophic mis-scaling when deterministic parsing fails. Dimension-based inference remains a fallback but is treated as unreliable unless corroborated.

- **Dependencies:** PRD 3 (geometry engine) and PRD 3.5 (validation) must be complete.

---

## Quality gates

Run these to validate PRD completion (unit + non-LLM integration only):

1. `cd backend && python -m pytest tests/ -v --tb=short -k 'not integration'`
2. `cd backend && python -m pytest tests/ --cov=cantena --cov-report=term-missing --cov-fail-under=75`
3. `cd backend && python -m mypy cantena/ --strict`
4. `cd backend && python -m ruff check cantena/ tests/`

> LLM integration tests are opt-in and skipped if `ANTHROPIC_API_KEY` is not set.

---

## Engineering principles

- **Polygon accuracy over hull heuristics:** prefer polygon reconstruction (`polygonize`) over convex hull for area.
- **No “linchpin regex”:** scale must be robust, multi-path, and never a single point of failure.
- **LLM is enhancement, not dependency:** core measurements must still run without an API key; LLM adds validation + enrichment.

---

## User stories

### US-371 — Endpoint snapping: close near-miss gaps in wall segments

- **Category:** core
- **Title:** Endpoint snapping: close near-miss gaps in wall segments
- **Description:**  
  As a developer, I want wall segment endpoints that are within a small tolerance of each other to be snapped together so that Shapely `polygonize()` can form closed room polygons from wall lines that have tiny CAD-export gaps.

#### Acceptance criteria

- `cantena/geometry/snap.py` defines `snap_endpoints(segments: list[WallSegment], tolerance_pts: float = 3.0) -> list[WallSegment]`
- The function collects all unique endpoints, finds clusters of points within `tolerance_pts`, replaces each cluster with its centroid, and returns new `WallSegment` objects with snapped endpoints
- Clustering uses simple `O(n^2)` pairwise distance check (acceptable for <200 segments); document KDTree upgrade path if needed
- Helper `snap_to_grid(point: Point2D, grid_size_pts: float = 1.0) -> Point2D` rounds coordinates to nearest grid point (optional regularization)
- After snapping, duplicate segments (same start/end after snapping) are removed
- Tests in `tests/test_snap.py`:
  1. Endpoints 2pts apart snap together
  2. Endpoints 5pts apart do **not** snap
  3. Duplicate segments removed
  4. Grid snapping rounds correctly
  5. Empty input returns empty
  6. Exactly matching endpoints unchanged
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  `polygonize()` needs exact endpoint equality. Snapping within a small tolerance fixes CAD-export floating-point gaps without meaningfully distorting geometry.

---

### US-372 — Room polygon reconstruction via Shapely polygonize

- **Category:** core
- **Title:** Room polygon reconstruction via Shapely polygonize
- **Description:**  
  As a developer, I want to reconstruct enclosed room polygons from wall segments using Shapely’s `polygonize()` so that I can compute individual room areas instead of relying on convex hull.

#### Acceptance criteria

- `cantena/geometry/rooms.py` defines `RoomDetector` class
- `RoomDetector.detect_rooms(segments: list[WallSegment], scale: ScaleResult | None = None) -> RoomAnalysis`:
  1. Snap endpoints using `snap_endpoints` (US-371)
  2. Extend wall segments slightly at endpoints (by 1pt) to improve intersections (T-junctions)
  3. Convert `WallSegment`s to Shapely `LineString`s
  4. Union linework with `shapely.ops.unary_union`
  5. Call `shapely.polygonize()` on noded linework
  6. Filter polygons:
     - remove tiny polygons (< 100 sq pts)
     - remove the largest polygon if it’s likely page boundary/title block (> 80% of page area)
  7. Return `RoomAnalysis`
- `RoomAnalysis` model (frozen dataclass):
  - `rooms: list[DetectedRoom]`
  - `total_area_pts: float`
  - `total_area_sf: float | None` (if scale)
  - `room_count: int`
  - `outer_boundary_polygon: Polygon | None`
  - `polygonize_success: bool`
- `DetectedRoom` model (frozen dataclass):
  - `polygon_pts: list[tuple[float, float]]`
  - `area_pts: float`
  - `area_sf: float | None`
  - `perimeter_pts: float`
  - `perimeter_lf: float | None`
  - `centroid: Point2D`
  - `label: str | None`
  - `room_index: int`
- If `polygonize()` produces 0 rooms, fall back to convex hull from existing `WallDetector`; set `polygonize_success=False`
- Tests in `tests/test_rooms.py`:
  1. Rectangle -> 1 room polygon with correct area
  2. Two adjacent rooms -> 2 polygons
  3. Small gaps (2pts) snapped -> still produces rooms
  4. Non-closing segments -> fallback hull (`polygonize_success=False`)
  5. Tiny artifacts filtered
  6. Area converts to SF when scale provided
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This is the main accuracy upgrade vs convex hull, especially on drawings with porches / recesses / dead space.

---

### US-373 — Room label matching: associate text labels with detected room polygons

- **Category:** core
- **Title:** Room label matching: associate text labels with detected room polygons
- **Description:**  
  As a developer, I want to associate room name labels (text blocks like “LIVING ROOM”) with detected room polygons so each room has a name without needing the LLM.

#### Acceptance criteria

- `cantena/geometry/rooms.py` extended with:
  - `RoomDetector.label_rooms(rooms: RoomAnalysis, text_blocks: list[TextBlock]) -> RoomAnalysis`
- Match text blocks against a curated list of common room names (case-insensitive):  
  LIVING ROOM, KITCHEN, DINING, BEDROOM, BATHROOM, RESTROOM, WC, UTILITY, LAUNDRY, CORRIDOR, HALLWAY, CLOSET, STORAGE, OFFICE, CONFERENCE, LOBBY, ENTRY, FOYER, GARAGE, PORCH, DECK, MECHANICAL, etc.
- For matched labels:
  - find the polygon containing the text position (`Point.within(Polygon)`)
  - if none contains, assign to nearest centroid within 50pts
- Update `DetectedRoom.label`
- Handle edge cases:
  - multiple labels inside one room (use first/most prominent)
  - one label outside all rooms (assign nearest)
  - duplicate labels (append index: “BEDROOM 1”, “BEDROOM 2”)
- Tests in `tests/test_room_labels.py`:
  1. Label inside polygon assigns correctly
  2. Label outside assigns to nearest
  3. Non-room text ignored
  4. Unlabeled rooms remain `None`
  5. Duplicate names get indexed
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This is “no-AI room naming” using spatial containment + a curated vocabulary.

---

### US-374 — LLM-assisted geometry interpretation service

- **Category:** core
- **Title:** LLM-assisted geometry interpretation service
- **Description:**  
  As a developer, I want an LLM service that takes extracted geometry data (rooms, measurements, text) and the PDF page image, and uses Claude to produce richer semantic analysis and a structured SpaceProgram.

#### Acceptance criteria

- `cantena/services/llm_geometry_interpreter.py` defines `LlmGeometryInterpreter` taking an API key in constructor
- `LlmGeometryInterpreter.interpret(geometry_summary: GeometrySummary, page_image_path: Path | None = None) -> LlmInterpretation` sends structured data to Claude and parses structured JSON output
- `GeometrySummary` (frozen dataclass):
  - `scale_notation: str | None`
  - `scale_factor: float | None`
  - `total_area_sf: float | None`
  - `rooms: list[RoomSummary]` (room_index, label, area_sf, perimeter_lf)
  - `all_text_blocks: list[str]`
  - `wall_count: int`
  - `measurement_confidence: str`
- `RoomSummary` model: room_index, label, area_sf, perimeter_lf
- Prompt instructs Claude to confirm/flag room IDs, infer building type/system, flag anomalies, extract special conditions; output JSON
- Response parsed into `LlmInterpretation`:
  - `building_type: str`
  - `structural_system: str`
  - `rooms: list[LlmRoomInterpretation]` (room_index, confirmed_label, room_type_enum, notes)
  - `special_conditions: list[str]`
  - `measurement_flags: list[str]`
  - `confidence_notes: str`
- If `page_image_path` provided, send as vision input
- Timeout 30s; if API call fails, return default `LlmInterpretation` with UNKNOWN fields (LLM is enhancement, not dependency)
- Uses Anthropic SDK directly (not VlmAnalyzer)
- Tests in `tests/test_llm_geometry_interpreter.py`:
  1. Mocked API JSON parsed correctly
  2. Malformed response -> default fallback
  3. Timeout -> default fallback
  4. GeometrySummary serializes correctly
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  LLM validates/enriches computed geometry rather than guessing measurements from pixels.

---

### **US-378 — Scale verification safety rail via LLM (linchpin protection)**

- **Category:** core
- **Title:** Scale verification safety rail via LLM (linchpin protection)
- **Description:**  
  As a developer, I want scale detection to be _verified_ (and optionally recovered) via an LLM-assisted check so that a brittle title-block parse or unreliable dimension inference cannot silently produce massively wrong areas (scale² error).

#### Acceptance criteria

- Add `cantena/geometry/scale_verify.py` defining `ScaleVerifier` (or extend `ScaleDetector` cleanly) with:
  - `verify_or_recover_scale(page: fitz.Page, detected: ScaleResult | None, text_blocks: list[TextBlock]) -> ScaleVerificationResult`
- `ScaleVerificationResult` model includes:
  - `scale: ScaleResult | None` (final chosen scale)
  - `verification_source: Literal["DETERMINISTIC", "LLM_CONFIRMED", "LLM_RECOVERED", "UNVERIFIED"]`
  - `warnings: list[str]` (e.g., “LLM disagreed with deterministic parse by 22%”)
  - `llm_raw_notation: str | None`
- Inputs to the LLM scale verifier must be _narrow and explainable_:
  - title-block region text (either by selecting text blocks in bottom-right area, or by “lines near SCALE”)
  - a short list of candidate scale strings found on page (top N matches)
  - optionally a rendered **crop image** of the title block (preferred if available)
- LLM request asks for strict JSON:
  - `{"notation": "...", "paper_inches": <float>, "real_inches": <float>, "scale_factor": <float>, "confidence": "HIGH|MEDIUM|LOW"}`
- Decision logic (must be deterministic and logged):
  - If `detected` is HIGH confidence (exact parse) and LLM agrees within ±5% → keep detected, mark `LLM_CONFIRMED`
  - If `detected` is LOW/MEDIUM or None and LLM returns HIGH/MEDIUM → adopt LLM scale (`LLM_RECOVERED`)
  - If LLM disagrees strongly with a HIGH-confidence detected scale (e.g., >10%) → keep detected **but** attach warning and downgrade downstream measurement confidence unless user override exists
  - Dimension-based inference is allowed but treated as **unreliable unless corroborated** (e.g., by title block parse or LLM)
- If API key missing or LLM fails/timeouts/429:
  - do not fail the pipeline
  - return `verification_source="UNVERIFIED"` and proceed with best deterministic scale (or None)
- Unit tests in `tests/test_scale_verify.py` (mocked API):
  1. Deterministic HIGH + LLM agrees → confirmed
  2. Deterministic None + LLM recovers → recovered
  3. Disagreement case emits warning and does not silently swap scale
  4. Timeout/429 returns UNVERIFIED and does not crash
- Add an opt-in integration test (real API) in `tests/integration/test_first_floor_scale_llm.py`:
  - skip if `ANTHROPIC_API_KEY` missing
  - assert LLM-verifier returns ~48.0 (±2) for `first-floor.pdf`
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This makes scale robust without “AI-everything.” The LLM is a guardrail and recovery tool for the one place where being wrong explodes downstream.

---

### US-375 — Update MeasurementService to use room-based area computation

- **Category:** integration
- **Title:** Update MeasurementService to use room-based area computation
- **Description:**  
  As a developer, I want MeasurementService to use polygonize-based RoomDetector for area computation and optionally run LLM enrichment so PageMeasurements includes per-room data and improved total area.

#### Acceptance criteria

- `MeasurementService` (`cantena/geometry/measurement.py`) updated:
  - `measure()` uses `RoomDetector.detect_rooms()` for area computation instead of (or in addition to) convex hull
- `PageMeasurements` extended:
  - `rooms: list[DetectedRoom] | None`
  - `room_count: int`
  - `polygonize_success: bool`
  - `llm_interpretation: LlmInterpretation | None`
  - **(additive)** `scale_verification: ScaleVerificationResult | None` (if ScaleVerifier is wired in)
- `MeasurementService` constructor takes:
  - optional `llm_interpreter: LlmGeometryInterpreter | None`
  - optional `scale_verifier: ScaleVerifier | None`
- Area computation priority:
  1. Sum polygonized room areas (HIGH)
  2. Convex hull (MEDIUM)
  3. Page-size estimate (LOW)
- Confidence reflects which area method + whether scale was verified/confirmed
- Backward compatible: existing tests still pass; room fields additive
- Tests in `tests/test_measurement_rooms.py`:
  1. Rooms included when polygonize works
  2. Polygonized total closer than convex hull on synthetic examples
  3. Fallback to convex hull when polygonize fails
  4. `room_count` + `polygonize_success` set correctly
  5. Without LLM interpreter, `llm_interpretation=None`
  6. With ScaleVerifier mocked, `scale_verification` is populated
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  The core measurement improvement is room-sum area. Scale verification feeds into confidence and reduces “silent wrong” outcomes.

---

### US-376 — Real API integration tests on first-floor.pdf

- **Category:** integration
- **Title:** Real API integration tests on first-floor.pdf
- **Description:**  
  As a developer, I want integration tests that run the enhanced pipeline (geometry + room detection + LLM interpretation) on `first-floor.pdf` using real API calls, so I can validate the end-to-end system beyond mocks.

#### Acceptance criteria

- `tests/integration/test_first_floor_llm.py` contains real API tests (NOT mocks)
- Mark tests with `@pytest.mark.llm`
- Skip if `ANTHROPIC_API_KEY` missing: `pytest.skip("ANTHROPIC_API_KEY not set — skipping LLM integration tests")`
- `test_llm_room_interpretation`:
  - run pipeline to get rooms + measurements
  - send to `LlmGeometryInterpreter` with real API
  - assert:
    - non-default interpretation returned
    - building_type is residential (any reasonable)
    - structural_system mentions wood frame or similar (joists)
    - > =3 rooms have confirmed labels
    - special_conditions mentions at least one of woodstove/chimney/hardwood/brick
- `test_llm_with_image`:
  - also send rendered page image
  - assert response returned and is equal/better in richness
- `test_full_pipeline_accuracy`:
  - total area from polygonized rooms in [400, 600] SF (expected ~512)
  - > =4 named rooms
  - scale factor ~48 ±5
  - LLM identifies residential
- `test_room_area_improvement_over_convex_hull`:
  - assert polygonize total is closer to 512 than convex hull total
- `test_measurement_report_with_rooms`:
  - generate `test_results/first-floor-enhanced-report.md` with per-room breakdown + LLM summary
- Rate limits:
  - if 429, `pytest.skip` rather than fail
- Quality gates pass (LLM tests are opt-in)

- **Passes:** false
- **Notes:**  
  The definitive proof: polygonize improves accuracy on a real plan, and the LLM enriches without being required for measurement.

---

### US-377 — Enhanced debug visualization with room polygons and labels

- **Category:** polish
- **Title:** Enhanced debug visualization with room polygons and labels
- **Description:**  
  As a developer, I want the debug visualization endpoint to show detected room polygons with labels and areas overlaid on the drawing.

#### Acceptance criteria

- `POST /api/debug/geometry` updated:
  - overlay includes:
    - each room polygon semi-transparent fill (different per room)
    - room label centered
    - room area (SF) below label
    - unlabeled rooms shown in gray with “?” + area
- JSON response extended:
  - `rooms[]`: room_index, label, area_sf, perimeter_lf, polygon vertices, centroid coords
- If LLM interpretation available, include `llm_interpretation` in JSON
- Backward compatible: if no rooms detected, keep existing wall overlay
- Tests in `tests/test_debug_rooms.py`:
  1. room-detectable PDF returns rooms in JSON
  2. PNG overlay modifies pixels in room areas
  3. without rooms, existing wall overlay works
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This becomes the best tuning + demo artifact: “here’s what we detected” directly on the drawing.
