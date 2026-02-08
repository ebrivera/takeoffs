# Cantena Geometry Engine — PRD (Vector PDF → Scale → Measurements → Hybrid VLM)

## Project metadata

- **Project:** cantena-geometry-engine
- **Branch:** ralph/geometry-engine
- **Description:**  
  A geometry extraction and measurement engine that pulls vector graphics (lines, rectangles, curves) directly from CAD-exported PDF construction drawings using PyMuPDF, calibrates them to real-world scale using title block notation and OCR'd dimension strings, and computes actual areas, perimeters, and wall lengths. This replaces VLM 'guessing' of square footage with computed measurements from the drawing geometry itself. The VLM still handles semantic interpretation (what type of building, what systems), but measurements come from the geometry engine. This is the accuracy leap that moves Cantena from 'lookup table with AI input' to 'actual measurement from drawings.' Depends on PRD 1 (cost engine) being complete. Integrates with PRD 2 (product pipeline) by replacing/augmenting VLM-only analysis.

---

## Quality gates

Run these to validate PRD completion:

1. `cd backend && python -m pytest tests/ -v --tb=short`
2. `cd backend && python -m pytest tests/ --cov=cantena --cov-report=term-missing --cov-fail-under=80`
3. `cd backend && python -m mypy cantena/ --strict`
4. `cd backend && python -m ruff check cantena/ tests/`

---

## User stories

### US-301 — Vector path extraction from PDF pages

- **Category:** core
- **Title:** Vector path extraction from PDF pages
- **Description:**  
  As a developer, I want to extract all vector drawing paths (lines, rectangles, curves) from a PDF page as structured coordinate data so that I can analyze the geometry of construction drawings programmatically rather than relying solely on pixel-based image analysis.

#### Acceptance criteria

- `cantena/geometry/extractor.py` defines `VectorExtractor` class
- `VectorExtractor.extract(page: fitz.Page) -> DrawingData` method uses PyMuPDF's `page.get_drawings()` to extract all vector paths
- `DrawingData` model contains:
  - paths (`list[VectorPath]`)
  - page_width_pts (`float`)
  - page_height_pts (`float`)
  - page_size_inches (`tuple[float, float]` computed from points at 72 pts/inch)
- `VectorPath` model contains:
  - path_type (`line | rect | curve | polyline`)
  - points (`list[Point2D]` the coordinates)
  - stroke_color (`tuple[float, float, float] | None`)
  - fill_color (`tuple[float, float, float] | None`)
  - line_width (`float`)
  - bounding_rect (`BoundingRect` with x, y, width, height in PDF points)
- `Point2D` is a simple model with x (`float`) and y (`float`) in PDF coordinate space (points)
- Lines extracted as pairs of points, rectangles as 4 corners, curves as control points, polylines as sequences of connected points
- `VectorExtractor.filter_by_region(data: DrawingData, region: BoundingRect) -> DrawingData` returns only paths within or intersecting the given region for isolating drawing area from title block
- `VectorExtractor.get_stats(data: DrawingData) -> DrawingStats` returns path_count, line_count, rect_count, curve_count, total_line_length_pts, bounding_box of all geometry
- Tests in `tests/test_vector_extractor.py`:
  1. Create test PDF with known geometry using PyMuPDF Shape draw a rectangle and two lines, extract them back, verify coordinates match
  2. Filter by region excludes paths outside region
  3. Stats computed correctly
  4. Empty page returns empty DrawingData
  5. Page with only text returns empty paths list
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  Most construction PDFs are exported from CAD software (AutoCAD, Revit) and contain vector geometry. Walls, doors, windows, and dimension lines are stored as PDF drawing commands, not pixels. PyMuPDF `get_drawings()` returns these as structured dictionaries with coordinates, colors, and line properties. We normalize into clean models. Coordinate system is PDF points (72 points = 1 inch on printed page). The filter_by_region method is important for excluding title block border and annotation areas.

---

### US-302 — Scale detection: parse title block and dimension annotations

- **Category:** core
- **Title:** Scale detection: parse title block and dimension annotations
- **Description:**  
  As a developer, I want to automatically detect the drawing scale from title block text and dimension annotation strings so that I can convert PDF coordinate measurements into real-world feet and inches.

#### Acceptance criteria

- `cantena/geometry/scale.py` defines `ScaleDetector` class
- `ScaleDetector.detect_from_text(page_text: str) -> ScaleResult | None` parses common architectural scale notations:
  - `1/8" = 1'-0"`
  - `1/4" = 1'-0"`
  - `1:100`
  - `1:50`
  - `SCALE: 1/8"=1'0"`
  - `3/16"=1'-0"`
  - `1"=10'-0"` (site plans)  
    plus variants with inconsistent spacing and punctuation
- `ScaleResult` model:
  - drawing_units (`float`, inches on paper)
  - real_units (`float`, inches in real world)
  - scale_factor (`float`, real_units / drawing_units e.g. 96.0 for 1/8"=1'-0")
  - notation (`str`, original parsed text)
  - confidence (`HIGH` if exact pattern match, `MEDIUM` if fuzzy)
- `ScaleDetector.detect_from_dimensions(paths: list[VectorPath], texts: list[TextBlock]) -> ScaleResult | None` cross-references dimension lines (identified by characteristic arrow/tick endpoints and nearby text) with numeric values in nearby text blocks to infer scale
- `TextBlock` model:
  - text (`str`)
  - position (`Point2D` center)
  - bounding_rect (`BoundingRect`)
- `ScaleDetector.extract_text_blocks(page: fitz.Page) -> list[TextBlock]` uses PyMuPDF text extraction to get all text with positions
- Helper `parse_dimension_string(text: str) -> float | None` parses:
  - `24'-6"`
  - `24'6"`
  - `24.5'`
  - `10'-0"`
  - `150'-0"`  
    into inches (294.0 for `24'-6"`)
- Tests in `tests/test_scale.py`:
  1. Parse common scale notations (1/8"=1'-0" -> factor 96, 1/4"=1'-0" -> factor 48, 3/16"=1'-0" -> factor 64, 1"=10'-0" -> factor 120)
  2. Parse dimension strings (24'-6" -> 294, 10'-0" -> 120)
  3. Handle messy text with extra spaces, different quote styles
  4. Return None for unparseable text
  5. detect_from_text finds scale in block of title block text containing other content
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  Scale detection is THE critical step for turning PDF geometry into real-world measurements. Architectural scales are standard: 1/8"=1'-0" most common for floor plans (1 inch on paper = 8 feet, scale factor = 96). Site plans use 1"=10'-0" or 1"=20'-0". Detail drawings use 1/2"=1'-0" or 3/4"=1'-0". Title block almost always states scale explicitly, but text can be messy. The dimension-based inference is a fallback that calibrates from actual annotated dimensions — this is how Bluebeam and PlanSwift do manual calibration.

---

### US-303 — Wall detection and room boundary identification

- **Category:** core
- **Title:** Wall detection and room boundary identification
- **Description:**  
  As a developer, I want to identify wall lines in the vector geometry so that I can detect room boundaries and compute floor areas from the actual drawing geometry.

#### Acceptance criteria

- `cantena/geometry/walls.py` defines `WallDetector` class
- `WallDetector.detect(data: DrawingData) -> WallAnalysis` identifies probable wall segments from vector paths
- Wall detection heuristics:
  - (a) Lines with heavier stroke width (walls use 0.5mm+ vs 0.13mm for dims/annotations)
  - (b) Lines strictly horizontal or vertical (plus or minus 2 degrees)
  - (c) Pairs of parallel lines close together (wall thickness 4-12 inches at scale)
  - (d) Lines with wall-typical colors (black, dark gray, not red/blue/green typically used for MEP/annotations)
- `WallSegment` model:
  - start (`Point2D`)
  - end (`Point2D`)
  - thickness_pts (`float | None`)
  - orientation (`HORIZONTAL | VERTICAL | ANGLED`)
  - length_pts (`float`)
- `WallAnalysis` model:
  - segments (`list[WallSegment]`)
  - total_wall_length_pts (`float`)
  - detected_wall_thickness_pts (`float | None` median)
  - outer_boundary (`list[Point2D] | None`, convex hull or bounding polygon of outermost walls)
- `WallDetector.compute_enclosed_area_pts(segments: list[WallSegment]) -> float | None` computes gross floor area by finding largest enclosed region using Shapely Polygon from outer boundary points
- Shapely library added to dependencies for polygon operations
- Tests in `tests/test_walls.py`:
  1. Create test PDF with thick lines forming rectangle (walls) and thin lines inside (annotations), verify thick lines detected
  2. Two parallel lines 6pts apart detected as wall pair
  3. Compute enclosed area of simple rectangular plan
  4. Filter out thin lines correctly
  5. No walls detected returns empty analysis not error
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  Wall detection from vector data is a key differentiator. In CAD-exported PDFs, walls are drawn with specific line weights — architects use heavy lineweight for walls (0.50mm or 0.70mm pen) and light for dimensions (0.13mm). This convention has been standard since hand drafting. Heuristics won't be perfect but for well-formed CAD PDFs (what GCs receive from architects), lineweight alone catches 80%+ of walls. Shapely handles irregular shapes, holes, and area calculation cleanly.

---

### US-304 — Scaled measurement service: PDF geometry to real-world dimensions

- **Category:** core
- **Title:** Scaled measurement service: PDF geometry to real-world dimensions
- **Description:**  
  As a developer, I want a service that combines vector extraction + scale detection + wall analysis to produce real-world measurements (square feet, linear feet of wall, building perimeter) from a PDF page.

#### Acceptance criteria

- `cantena/geometry/measurement.py` defines `MeasurementService` class taking `VectorExtractor`, `ScaleDetector`, and `WallDetector`
- `MeasurementService.measure(page: fitz.Page) -> PageMeasurements` runs full pipeline on single page
- `PageMeasurements` model:
  - scale (`ScaleResult | None`)
  - gross_area_sf (`float | None`)
  - building_perimeter_lf (`float | None`)
  - total_wall_length_lf (`float | None`)
  - wall_count (`int`)
  - confidence (`MeasurementConfidence` enum:
    - `HIGH` if scale from title block + walls detected
    - `MEDIUM` if scale found but walls uncertain
    - `LOW` if scale inferred from page size
    - `NONE` if no measurements)
  - raw_data (`DrawingData` for debugging)
- Conversion functions:
  - `pts_to_real_sf(pts_squared: float, scale: ScaleResult) -> float`
  - `pts_to_real_lf(pts: float, scale: ScaleResult) -> float`  
    Area: `area_sf = area_pts * (1/72)^2 * scale_factor^2 / 144`  
    Length: `length_lf = length_pts * (1/72) * scale_factor / 12`
- Graceful fallbacks:
  - No vector data -> `NONE`
  - Vector data no scale -> estimate from page size (standard sheets: 24x36, 30x42) -> `LOW`
  - Walls detected no closed boundary -> convex hull area -> `MEDIUM`
- Tests in `tests/test_measurement.py`:
  1. Test PDF at known scale with 100'x50' rectangle at 1/8"=1'-0" (900pts x 450pts on paper), verify area ~5000 SF +/-5%
  2. Verify perimeter ~300 LF +/-5%
  3. Conversion functions with known values
  4. No vector data returns `NONE`
  5. Missing scale returns `LOW` confidence
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This is where geometry becomes measurements a PM cares about. Conversion math: PDF coordinates are in points (72/inch), scale factor converts paper inches to real inches. A line 72pts long = 1 inch on paper. At 1/8"=1'-0" (factor 96), that represents 96 inches = 8 feet. For area: square the factor and divide by 144 for SF. The fallback chain ensures we always try to give something rather than failing. The test with a precisely-drawn rectangle at known scale proves the math end-to-end.

---

### US-305 — Hybrid analysis: merge geometry measurements with VLM semantic analysis

- **Category:** integration
- **Title:** Hybrid analysis: merge geometry measurements with VLM semantic analysis
- **Description:**  
  As a developer, I want to merge geometry-computed measurements with VLM-extracted semantic information so the cost engine gets accurate areas from geometry and building type identification from the VLM.

#### Acceptance criteria

- `cantena/services/hybrid_analyzer.py` defines `HybridAnalyzer` taking `MeasurementService` and `VlmAnalyzer`
- `HybridAnalyzer.analyze(page: fitz.Page, image_path: Path, context: AnalysisContext | None = None) -> HybridAnalysisResult` runs both geometry and VLM on same page
- `HybridAnalysisResult` model:
  - building_model (`BuildingModel` merged)
  - geometry_measurements (`PageMeasurements`)
  - vlm_result (`VlmAnalysisResult`)
  - merge_decisions (`list[MergeDecision]`)
- `MergeDecision` model:
  - field_name (`str`)
  - source (`GEOMETRY | VLM | USER_OVERRIDE`)
  - value (`str`)
  - reasoning (`str`)
  - confidence (`Confidence`)
- Merge logic per field:
  - gross_sf uses geometry if `HIGH/MEDIUM` confidence else VLM
  - stories/building_type/structural_system/exterior_wall/mechanical_system always VLM (semantic)
  - story_height VLM
  - location from context
  - complexity_scores VLM
  - special_conditions merges both
- Merged `BuildingModel.confidence` dict reflects actual source: geometry-measured fields get `HIGH` if geometry was `HIGH`
- Tests in `tests/test_hybrid_analyzer.py`:
  1. Geometry HIGH 45000 SF + VLM 42000 SF -> merged uses 45000
  2. Geometry NONE -> falls back to VLM
  3. Building type always from VLM
  4. Merge decisions documented
  5. Geometry anomalies added to special_conditions
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  This architecture makes us better than either pure CV or pure VLM. VLM is great at 'this is a steel-frame office with curtain wall' (semantic interpretation). But VLM is mediocre at 'this is 45,000 SF' (eyeballing proportions). Geometry engine is the opposite: precise area measurement, no idea what curtain wall is. Together: accurate measurements AND correct classification. MergeDecision log is crucial for trust — PM sees 'Gross SF: 45,230 (source: geometry, confidence: HIGH)' vs 'Structural System: Steel Frame (source: AI, confidence: MEDIUM)'.

---

### US-306 — Update pipeline to use hybrid analysis

- **Category:** integration
- **Title:** Update pipeline to use hybrid analysis
- **Description:**  
  As a developer, I want the AnalysisPipeline to use HybridAnalyzer when vector geometry is available so the /api/analyze endpoint automatically gets more accurate measurements without frontend changes.

#### Acceptance criteria

- AnalysisPipeline updated to optionally use `HybridAnalyzer`
- Pipeline logic:
  1. Process PDF to images
  2. Extract vector data from page using `VectorExtractor`
  3. If vector data has >50 paths (real drawing), use `HybridAnalyzer`. Else VLM-only
  4. Return enhanced `PipelineResult`
- `PipelineResult` extended:
  - geometry_available (`bool`)
  - measurement_confidence (`MeasurementConfidence`)
  - merge_decisions (`list[MergeDecision] | None`)
- `/api/analyze` response includes geometry_available and measurement_confidence
- Backward compatible: without HybridAnalyzer configured, falls back to VLM-only
- Tests:
  1. Vector-rich PDF uses HybridAnalyzer
  2. Scanned PDF falls back to VLM-only
  3. PipelineResult includes geometry fields
  4. Backward compatible without HybridAnalyzer
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  Drop-in upgrade. Frontend unchanged, but measurements are computed from actual geometry when available. The >50 paths threshold distinguishes real CAD geometry from border/annotation marks. Typical floor plan has hundreds to thousands of paths. Graceful fallback means scanned PDFs still work via VLM-only, CAD-exported PDFs get accuracy boost automatically.

---

### US-307 — Geometry debug visualization endpoint

- **Category:** polish
- **Title:** Geometry debug visualization endpoint
- **Description:**  
  As a developer testing geometry detection, I want a debug endpoint that overlays detected walls and measurements on the original drawing so I can visually verify accuracy.

#### Acceptance criteria

- `GET /api/debug/geometry` accepts PDF upload, returns PNG with overlay
- Overlay:
  - detected walls in red
  - outer boundary in blue
  - area text
  - scale notation
  - confidence badge
- Uses PyMuPDF to render base image, Pillow for overlays
- Also returns JSON: raw measurements, wall segments, scale, stats
- Tests:
  1. Returns 200 with PNG for valid PDF
  2. JSON includes measurements
  3. Returns 400 for non-PDF
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  Essential for tuning wall detection heuristics. Upload a real construction PDF, see what geometry engine thinks is a wall vs what it ignores. Red lines overlaid make it obvious. This is how you iterate: upload WT drawing, look at overlay, adjust thresholds, repeat. Also becomes a powerful demo tool — show PMs 'here is what our AI measured' overlaid on their own drawings.
