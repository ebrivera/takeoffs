# Cantena Geometry Validation — PRD (Real Drawing Integration Suite)

## Project metadata

- **Project:** cantena-geometry-validation
- **Branch:** ralph/geometry-validation
- **Description:**  
  An integration test suite that validates the entire geometry engine (PRD 3) against a real architectural drawing: `test_pdfs/first-floor.pdf`. This is a 1st floor plan for an American Farmhouse drawn at 1/4"=1'-0" scale with explicit dimensions (32' x 16' overall), named rooms (Living Room, Kitchen, Dining, Front Porch, Back Porch, Utility, WC, Coats, Laundry), and standard CAD conventions. Every geometry engine component — vector extraction, scale detection, wall detection, measurement, and the hybrid pipeline — is tested against known ground-truth values from this real drawing. If the geometry engine can correctly measure this drawing, it can measure real construction documents.

> **Repo assumption (to keep tests simple):** store the fixture at `backend/test_pdfs/first-floor.pdf` (so tests under `backend/tests/...` can resolve it without relying on the repo root).

---

## Quality gates

Run these to validate PRD completion:

1. `cd backend && python -m pytest tests/ -v --tb=short`
2. `cd backend && python -m pytest tests/ --cov=cantena --cov-report=term-missing --cov-fail-under=75`
3. `cd backend && python -m mypy cantena/ --strict`
4. `cd backend && python -m ruff check cantena/ tests/`

---

## Engineering principle

**No single-point-of-failure parsing.**  
If title block scale parsing fails due to formatting variance, the geometry engine must still produce usable measurements via dimension-calibration or graceful degradation. Any API-based text normalization is **optional** and must not be required for the engine to function.

---

## User stories

### US-351 — Test fixture: load and introspect the real floor plan PDF

- **Category:** setup
- **Title:** Test fixture: load and introspect the real floor plan PDF
- **Description:**  
  As a developer, I want a reusable test fixture that loads `test_pdfs/first-floor.pdf` and provides basic introspection so that all subsequent test stories can reference the same PDF with consistent setup.

#### Acceptance criteria

- `tests/conftest.py` (or `tests/integration/conftest.py`) defines a pytest fixture `first_floor_pdf` that opens `test_pdfs/first-floor.pdf` using PyMuPDF and yields the `fitz.Document`, closing it after the test completes
- A second fixture `first_floor_page` that yields the first (and only) page of the document as `fitz.Page`
- A constants file or fixture providing ground truth values for this specific drawing:
  - `EXPECTED_SCALE_FACTOR = 48.0` (1/4"=1'-0")
  - `EXPECTED_OVERALL_WIDTH_FT = 32.0`
  - `EXPECTED_OVERALL_DEPTH_FT = 16.0`
  - `EXPECTED_GROSS_AREA_SF = 512.0` (32 x 16, the main building footprint excluding porches)
  - `EXPECTED_TOTAL_WITH_PORCHES_SF` (approximate, including front and back porches)
  - `EXPECTED_ROOM_COUNT = at least 7` (Living Room, Kitchen, Dining, Utility, WC, Coats, Laundry — porches may or may not be detected as rooms)
- A smoke test in `tests/integration/test_first_floor_smoke.py` that verifies:
  - (a) PDF loads without error
  - (b) has exactly 1 page
  - (c) page has non-zero dimensions
  - (d) page contains text (not a scanned image)
- The test file path is resolved robustly so tests work from any working directory. Recommended pattern (assuming fixture lives at `backend/test_pdfs/...`):
  - `Path(__file__).resolve().parents[2] / "test_pdfs" / "first-floor.pdf"` for files under `backend/tests/integration/`
- All quality gates pass

- **Passes:** false
- **Notes:**  
  The ground truth values come directly from reading the uploaded drawing. The main building footprint is 32' wide x 16' deep = 512 SF. This is just the main structure — porches extend beyond. The scale is explicitly stated on the drawing: `SCALE: 1/4" =1'-0"` which means 1/4 inch on paper = 1 foot in reality, so 1 inch = 4 feet = 48 inches, giving scale_factor = 48. Dimension strings on the drawing confirm: `32'` across the top, `16'` on the sides. The room names are clearly labeled. We use approximate ranges in assertions (±10–15%) because the geometry engine won't be pixel-perfect — wall thicknesses, rounding, and detection imprecision all contribute small errors. The point is to be in the right ballpark, not exact to the inch.

---

### US-352 — Validate vector extraction on the real floor plan

- **Category:** core
- **Title:** Validate vector extraction on the real floor plan
- **Description:**  
  As a developer, I want to verify that the VectorExtractor correctly pulls meaningful geometry from first-floor.pdf so that I know the PDF contains usable CAD vector data and the extractor handles it properly.

#### Acceptance criteria

- `tests/integration/test_first_floor_vectors.py` uses the `first_floor_page` fixture
- Test: `VectorExtractor.extract()` returns `DrawingData` with a substantial number of paths — assert at least 50 paths
- Test: `DrawingStats` shows a mix of path types — assert `line_count > 20`, `rect_count >= 0` (rectangles may be represented as polylines in some CAD exports)
- Test: The bounding box of all geometry approximately matches the expected drawing area:
  - bounding box width is at least 50% of page width
  - bounding box height is at least 40% of page height
- Test: Vector paths have varying line widths — assert at least 2 distinct `line_width` values exist
  - Print/log the distribution of line widths found for debugging (e.g., `Found line widths: {0.24: 145, 0.72: 87, 1.44: 23}`)
- Test: Vector paths have color information — assert most paths have `stroke_color` defined (not None). Black/dark gray should be the majority
- Test: `filter_by_region` works — define a region covering the left half of the drawing area, filter, assert fewer paths than unfiltered
- If the PDF does NOT contain vector data (all content is rasterized images), document this finding clearly in a test comment and skip vector-dependent tests with:
  - `pytest.skip("PDF is rasterized, not vector — geometry engine requires CAD-exported PDFs")`
- All quality gates pass

- **Passes:** false
- **Notes:**  
  This is the “does the PDF have what we need” test. CAD-exported PDFs contain vector geometry. Scanned/print workflows may contain only raster images — geometry engine can’t work with those. The line width distribution is extremely valuable debugging info — it tells us exactly what thresholds to use for wall detection.

---

### US-353 — Validate scale detection on the real floor plan (no brittle regex dependency)

- **Category:** core
- **Title:** Validate scale detection on the real floor plan (no brittle regex dependency)
- **Description:**  
  As a developer, I want to verify that the ScaleDetector correctly identifies the 1/4"=1'-0" scale from this drawing in a way that is resilient to formatting variance, so the geometry engine is not dependent on a single brittle regex.

#### Acceptance criteria

- `tests/integration/test_first_floor_scale.py` uses the `first_floor_page` fixture

- Test: `extract_text_blocks` returns text blocks from the page — assert at least 20 text blocks found. Print the first 30 text blocks for debugging

- **Primary parsing must not be a single regex:**  
  `ScaleDetector.detect_from_text(page_text: str)` uses a two-step approach:
  1. **Text normalization** (quotes/unicode, spacing, separators) into a canonical form
  2. **Tolerant parsing** of architectural scale notation using a small grammar / tokenization approach  
     (Regex may be used as a helper, but not as the sole mechanism.)

- Test: `detect_from_text` correctly finds and parses the scale:
  - extract all page text, pass to `detect_from_text`
  - assert it returns a `ScaleResult` with `scale_factor` approximately 48.0 (±2)
  - if the exact text format isn’t matched, document what format was found and fix normalization/parsing (not just “add another regex”)

- Test: `parse_dimension_string` correctly parses dimension strings found on this drawing:
  - `'32'` -> 384 inches
  - `'16'` -> 192
  - `6'-6"` -> 78
  - `5'-6"` -> 66
  - `3'-4"` -> 40
  - `2'-8"` -> 32
  - `'8'` -> 96
  - `1'-6"` -> 18
  - `9'-8"` -> 116
  - `3'-1"` -> 37
  - `2'-1"` -> 25

- Test: `detect_from_dimensions` attempts to infer scale from dimension lines + text:
  - if successful, assert inferred `scale_factor` within ±15% of 48.0
  - otherwise document why inference failed

- **Optional API fallback (not required):**
  - `ScaleDetector` supports an optional `ScaleTextInterpreter` interface:
    - `interpret(raw_text: str) -> str` returns a normalized string (or JSON) that can be parsed deterministically
  - This interpreter may be backed by an API call (e.g., “normalize this title block scale notation into canonical ASCII”)
  - The engine must behave correctly if the interpreter is **not configured** (no env var, no key)

- Test: when `detect_from_text` fails on a deliberately “messy formatting” variant, the system still produces a usable scale by:
  - succeeding via normalization/parsing improvements **or**
  - falling back to `detect_from_dimensions` **or**
  - returning `None` but allowing `MeasurementService` to degrade gracefully (LOW/NONE confidence)  
    The goal is: **no hard failure due to text format.**

- All quality gates pass

- **Passes:** false
- **Notes:**  
  Title block scale strings vary a lot (spacing, quote types, separators). We avoid a single brittle regex by normalizing text and parsing via tokens/grammar. An API text-normalization fallback is allowed, but it must be optional and never the sole path. Dimension calibration remains the best non-text fallback.

---

### US-354 — Validate wall detection and area computation on the real floor plan

- **Category:** core
- **Title:** Validate wall detection and area computation on the real floor plan
- **Description:**  
  As a developer, I want to verify that the WallDetector correctly identifies the structural walls of this farmhouse and computes an area close to the known 32'×16' = 512 SF footprint so that I have confidence the geometry engine produces accurate measurements on real drawings.

#### Acceptance criteria

- `tests/integration/test_first_floor_walls.py` uses the `first_floor_page` fixture and vector data from US-352
- Test: `WallDetector.detect()` returns `WallAnalysis` with a non-trivial number of wall segments — assert at least 8 segments
- Test: Detect both orientations — assert at least 3 HORIZONTAL and at least 3 VERTICAL segments
- Test: Total detected wall length is in a reasonable range:
  - building perimeter alone is 96 LF, plus interior partitions likely add 40–80 LF
  - assert total wall length (after scale conversion) is between 80 LF and 250 LF
  - if outside, log segments with lengths for debugging
- Test: `outer_boundary` detection produces a polygon whose area is approximately 512 SF (±25%)
  - assert computed gross area between 380 SF and 700 SF
  - log computed area
- Test: Wall thickness detection (if detected) is reasonable:
  - assert detected thickness (real inches) between 3 and 12 inches
- Diagnostic logging test (non-assertion): print summary:
  - `Detected N walls: X horizontal (avg Y ft), Z vertical (avg W ft), thickness ~T inches`
- If wall heuristics are not tuned for this drawing, adjust thresholds in WallDetector and document the adjustments in `progress.txt`
- All quality gates pass

- **Passes:** false
- **Notes:**  
  This is the most important test story. The ±25% area tolerance is intentionally generous for the first pass. If the result is wildly off, wall detection needs tuning (line weight threshold, color filter, polyline handling, etc.). Diagnostics are required so you can see what the detector found.

---

### US-355 — Validate full MeasurementService pipeline on the real floor plan (graceful fallback)

- **Category:** core
- **Title:** Validate full MeasurementService pipeline on the real floor plan (graceful fallback)
- **Description:**  
  As a developer, I want to run the complete MeasurementService.measure() pipeline on first-floor.pdf and verify it produces a PageMeasurements result with realistic values, while ensuring scale detection is not a single point of failure.

#### Acceptance criteria

- `tests/integration/test_first_floor_measurement.py` uses the `first_floor_page` fixture

- Test: `MeasurementService.measure()` completes without error and returns a `PageMeasurements` object

- Test: **scale detection robustness**
  - On the real drawing, scale should be detected: `result.scale is not None` and `scale_factor ~ 48.0 (±5)`
  - Add a separate test case that injects a “mangled” scale text variant (via mocked text extraction) and asserts:
    - the pipeline still returns a result (does not crash)
    - confidence degrades appropriately if it can’t recover scale deterministically

- Test: `gross_area_sf` is in the right ballpark — assert between 350 and 800 SF (true ~512 SF; could be higher if porches included). Log actual value
- Test: `building_perimeter_lf` is reasonable — assert between 70 and 200 LF
- Test: `total_wall_length_lf` reasonable — assert between 80 and 300 LF
- Test: confidence is at least MEDIUM on the unmodified real drawing

- Diagnostic “report” test (always passes): print a formatted report (logged at WARNING) including % error vs 512 SF

- All quality gates pass

- **Passes:** false
- **Notes:**  
  The integration suite should enforce that the pipeline does not hinge on a single fragile parsing step. On clean drawings, we expect HIGH/MEDIUM confidence. On messy text, we expect graceful degradation, not failure.

---

### US-356 — Validate text and room label extraction for future room-type detection

- **Category:** integration
- **Title:** Validate text and room label extraction for future room-type detection
- **Description:**  
  As a developer, I want to verify that we can extract room labels and their positions from this drawing so that PRD 4's room-type-aware costing can map measured areas to named rooms.

#### Acceptance criteria

- `tests/integration/test_first_floor_rooms.py` uses the `first_floor_page` fixture
- Test: Extract all text blocks with positions. Assert we find text blocks containing (case-insensitive):
  - LIVING ROOM, KITCHEN, DINING, FRONT PORCH, BACK PORCH, UTILITY, WC, COATS, LAUNDRY
  - Log which were found/missed
- Test: Room labels’ positions fall within drawing content area (not title block/margins)
- Test: Room labels are spatially separated — no two label positions within 20 PDF points
- Test: Coarse zone mapping:
  - define zones (e.g., left half vs right half) and assert labels fall in expected zones
- Test: Dimension text extraction:
  - find text blocks matching dimension patterns, assert at least 10 dimension blocks found
- Test: Title block text extraction:
  - find text blocks in lower-right area and assert we find: SCALE, 1/4, A1.2, 1ST FLOOR, AMERICAN FARMHOUSE
- All quality gates pass

- **Passes:** false
- **Notes:**  
  This story validates the text extraction needed for room-type-aware costing later. Spatial accuracy matters: we need labels to land “inside” the correct room. The drawing also includes annotations that are not room labels — future work will distinguish labels vs notes.

---

### US-357 — Geometry accuracy report and known-limitations documentation

- **Category:** polish
- **Title:** Geometry accuracy report and known-limitations documentation
- **Description:**  
  As a developer, I want a comprehensive accuracy report for the geometry engine on this test drawing and documentation of known limitations so that the team understands exactly where we are and what needs improvement.

#### Acceptance criteria

- `tests/integration/test_first_floor_report.py` runs the full geometry pipeline and generates a detailed accuracy report saved to `test_results/first-floor-geometry-report.md`
- Report contains sections:
  - Drawing Info (filename, page size, scale detected, vector path count)
  - Measurement Results (gross area SF expected vs actual + % error, perimeter LF expected vs actual, wall count, wall length)
  - Text Extraction (room labels found, dimension strings found, title block fields found)
  - Confidence Assessment (overall confidence + per-component confidence)
- Report contains a Known Limitations section documenting issues discovered:
  - scale detection edge cases
  - wall detection false positives/negatives
  - area computation inaccuracies
  - text parsing failures  
    Each limitation includes severity (critical/moderate/minor) and suggested fix
- Report contains a Recommendations section:
  - what to tune for better accuracy
  - what VLM should handle vs what geometry should handle
  - what PDF classes work well vs poorly
- The report-generation test always passes (diagnostic tool) but **must** create the report file (create `test_results/` if it doesn’t exist)
- A separate assertion test verifies minimum thresholds:
  - Scale factor within ±10% of 48.0
  - Gross area within ±30% of 512 SF
  - At least 6 room labels extracted  
    If any threshold fails, fail with a clear message listing actual values
- All quality gates pass
- Report’s Known Limitations section must include whether title block scale parsing required:
  - deterministic normalization/parsing
  - dimension calibration fallback
  - optional API text interpreter
    And what percent of the time each path is used (for this fixture, just document which path was used).

- **Passes:** false
- **Notes:**  
  This is the capstone. The report is the single place to understand “how accurate are we on a real drawing?” The minimum thresholds are intentionally achievable for a clean, well-dimensioned plan. Over time, tighten tolerances (Phase 1 target ±15% area; production target ±10%).
