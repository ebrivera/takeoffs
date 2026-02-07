# Cantena Product Pipeline — PRD (PDF → VLM → Cost Engine → Web UI)

## Project metadata

- **Project:** cantena-product-pipeline
- **Branch:** ralph/product-pipeline
- **Description:**  
  The product layer for Cantena — PDF ingestion, VLM-based drawing analysis, FastAPI backend, and Next.js frontend. Depends on the cost engine foundation from PRD 1 (cantena-cost-engine). This PRD takes the standalone estimation library and turns it into a working web application: upload a construction floor plan PDF, get a conceptual budget in under 60 seconds. The pipeline is: PDF → images → VLM analysis → BuildingModel → CostEngine → CostEstimate → UI display.

---

## Quality gates

Run these to validate PRD completion:

1. `cd backend && python -m pytest tests/ -v --tb=short`
2. `cd backend && python -m mypy cantena/ --strict`
3. `cd backend && python -m ruff check cantena/ tests/`
4. `cd frontend && npm run typecheck`
5. `cd frontend && npm run lint`

---

## User stories

### US-101 — Frontend scaffolding: Next.js project with Tailwind

- **Category:** setup
- **Title:** Frontend scaffolding: Next.js project with Tailwind
- **Description:**  
  As a developer, I want a properly structured Next.js frontend project so that subsequent UI stories have a foundation to build on.

#### Acceptance criteria

- `frontend/` directory with a Next.js 14+ App Router project (TypeScript strict mode)
- Tailwind CSS configured and working
- ESLint and TypeScript strict mode configured in `tsconfig.json`
- A simple health-check page at `/` that renders `Cantena` as placeholder
- `package.json` has scripts: dev, build, lint, typecheck (tsc --noEmit)
- `frontend/lib/types.ts` defines TypeScript interfaces matching the Python CostEstimate, CostRange, DivisionCost, Assumption, BuildingSummary models from PRD 1 — these are the API contract
- `frontend/lib/api.ts` defines a typed fetch wrapper: `analyzePlan(file: File, location: {city: string, state: string}) -> Promise<CostEstimate>` that POSTs to `/api/analyze` (stubbed with a TODO for now)
- `npm run typecheck` and `npm run lint` pass

- **Passes:** false
- **Notes:**  
  Keep it simple. No component libraries, no state management libraries. Just Next.js, Tailwind, and TypeScript. The `types.ts` file is critical — it's the contract between frontend and backend. Generate it to match the Pydantic models exactly. The `api.ts` fetch wrapper ensures all API calls are typed end-to-end.

---

### US-102 — PDF processing service: PDF to high-res images

- **Category:** core
- **Title:** PDF processing service: PDF to high-res images
- **Description:**  
  As a developer, I want a service that takes a PDF file and produces high-resolution PNG images of each page so that the VLM can analyze construction drawings.

#### Acceptance criteria

- `cantena/services/pdf_processor.py` defines `PdfProcessor` class
- `PdfProcessor.process(pdf_path: Path) -> PdfProcessingResult` method converts PDF to images
- `PdfProcessingResult` contains: pages (list[PageResult]), page_count (int), file_size_bytes (int)
- `PageResult` contains:
  - page_number (int)
  - image_path (Path to PNG)
  - width_px (int)
  - height_px (int)
  - text_content (str — extracted text from the page via PyMuPDF)
  - title_block_text (str | None — text from bottom-right quadrant where title blocks typically are)
- Images are rendered at 200 DPI (good balance of quality vs VLM token cost — a 24x36 sheet becomes ~4800x7200px)
- PyMuPDF (fitz) used for both text extraction and image rendering — single dependency for both
- Temporary image files are written to a configurable output directory (default: system temp dir)
- `PdfProcessor.cleanup(result: PdfProcessingResult)` method deletes temporary image files
- Tests in `tests/test_pdf_processor.py`:
  1. Create a simple test PDF programmatically using reportlab or fitz, process it, assert page count and image files exist
  2. Text extraction returns content
  3. Cleanup deletes files
  4. Handles empty PDF gracefully (returns empty pages list)
  5. Handles non-PDF file with descriptive error
- Add PyMuPDF and Pillow to `pyproject.toml` dependencies
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  200 DPI is intentional. Higher DPI means bigger images, which means more VLM tokens and slower processing. 200 DPI on a 24x36 architectural sheet is plenty for a VLM to read annotations, dimensions, and room labels. The title_block_text extraction (bottom-right quadrant) is a cheap heuristic that gives us sheet name, scale, and project info without VLM cost. We use PyMuPDF for everything because it handles both text extraction and rasterization — no need for Poppler/pdf2image as a separate dependency.

---

### US-103 — VLM analysis service: image to BuildingModel

- **Category:** core
- **Title:** VLM analysis service: image to BuildingModel
- **Description:**  
  As a developer, I want a service that sends a construction drawing image to a VLM API and gets back a structured BuildingModel so that the cost engine can produce an estimate.

#### Acceptance criteria

- `cantena/services/vlm_analyzer.py` defines `VlmAnalyzer` class that takes an API key and model name in constructor
- `VlmAnalyzer.analyze(image_path: Path, context: AnalysisContext | None = None) -> VlmAnalysisResult` method sends image to Anthropic Messages API with vision and returns structured data
- `AnalysisContext` model:
  - project_name (str | None)
  - location (Location | None)
  - additional_notes (str | None)  
    Optional hints the user provides
- `VlmAnalysisResult` model:
  - building_model (BuildingModel)
  - raw_response (str — the VLM's full text response for debugging)
  - reasoning (str — the VLM's explanation of what it observed)
  - warnings (list[str] — anything the VLM flagged as uncertain or unusual)
- System prompt implements the multi-pass approach from the PRD: building identification, spatial analysis, system identification, complexity scoring — but in a single API call with structured instructions
- System prompt requires the VLM to:
  - (a) describe what it sees before extracting parameters
  - (b) explicitly state confidence for each field
  - (c) flag anything it's guessing about
  - (d) output a strict JSON block that matches BuildingModel schema
- Response parsing:
  - extract JSON from VLM response
  - validate against BuildingModel schema
  - handle malformed responses with a retry (max 1 retry with simplified prompt)
- If VLM cannot determine a required field, it uses a reasonable default and sets confidence to LOW
- Tests in `tests/test_vlm_analyzer.py`:
  1. Mock the Anthropic API client — do NOT make real API calls in tests
  2. Test that a well-formed mock response is correctly parsed into a BuildingModel
  3. Test that a malformed response triggers retry logic
  4. Test that missing fields get LOW confidence defaults
  5. Test that AnalysisContext location is passed through to the BuildingModel
- anthropic SDK added to `pyproject.toml` dependencies
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  CRITICAL: All tests must mock the Anthropic API. Never make real API calls in automated tests. Use unittest.mock or pytest-mock. The system prompt is key IP — it should be in a separate constant or file, not buried in method logic. The single-call approach (vs multiple VLM calls) saves cost and latency. We ask the VLM to 'think aloud' before outputting JSON because this improves accuracy (chain-of-thought). The retry on malformed response uses a simpler prompt: "Your previous response was not valid JSON. Please output ONLY a JSON object matching this schema: ...".

---

### US-104 — Analysis pipeline: orchestrate PDF → VLM → CostEngine

- **Category:** core
- **Title:** Analysis pipeline: orchestrate PDF → VLM → CostEngine
- **Description:**  
  As a developer, I want a pipeline service that orchestrates the full analysis flow so that the API endpoint has a single entry point for 'analyze this PDF'.

#### Acceptance criteria

- `cantena/services/pipeline.py` defines `AnalysisPipeline` class that takes `PdfProcessor`, `VlmAnalyzer`, and `CostEngine` in constructor
- `AnalysisPipeline.analyze(pdf_path: Path, project_name: str, location: Location) -> PipelineResult` method runs the full pipeline
- `PipelineResult` model:
  - estimate (CostEstimate)
  - analysis (VlmAnalysisResult)
  - processing_time_seconds (float)
  - pages_analyzed (int)
- Pipeline steps:
  1. Process PDF to images
  2. Select the best page for analysis — for MVP, use the first architectural floor plan page (heuristic: largest page, or page with 'floor plan' in title block text, or simply page 1)
  3. Run VLM analysis on selected page
  4. Run cost engine on resulting BuildingModel
  5. Cleanup temporary files
  6. Return combined result
- Error handling:
  - if PDF processing fails, raise descriptive error
  - if VLM fails, raise descriptive error
  - if cost engine fails (no matching cost data), raise descriptive error  
    Each error type is distinct so the API layer can return appropriate HTTP status codes
- Custom exception classes in `cantena/exceptions.py`:
  - PdfProcessingError
  - VlmAnalysisError
  - CostEstimationError  
    All inherit from `CantenaError` base
- Tests in `tests/test_pipeline.py`:
  1. Happy path with mocked PDF processor and VLM analyzer — assert CostEstimate is returned
  2. PDF processing error is wrapped in PdfProcessingError
  3. VLM error is wrapped in VlmAnalysisError
  4. Cost engine error is wrapped in CostEstimationError
  5. Cleanup is called even when analysis fails (use mock to verify)
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  The pipeline is intentionally simple for MVP — single page analysis only. Multi-page analysis (combining floor plans + elevations + structural sheets) is Phase 1 work. The page selection heuristic is good enough: construction PDFs typically have architectural plans first, and the floor plan is usually the largest sheet. The important thing is the pipeline structure is right so we can improve each stage independently.

---

### US-105 — FastAPI backend: /api/analyze endpoint

- **Category:** core
- **Title:** FastAPI backend: /api/analyze endpoint
- **Description:**  
  As a developer, I want a FastAPI application with an analyze endpoint so that the frontend can upload a PDF and get back a cost estimate.

#### Acceptance criteria

- `cantena/api/app.py` defines a FastAPI application
- `POST /api/analyze` endpoint accepts multipart form data:
  - file (UploadFile)
  - project_name (str)
  - city (str)
  - state (str)
- Endpoint saves uploaded file to temp directory, runs AnalysisPipeline, returns PipelineResult as JSON
- Response includes the full CostEstimate with summary_dict and export_dict from PRD 1 formatting helpers
- Error responses:
  - 400 for invalid file type (not PDF)
  - 422 for missing required fields
  - 500 for pipeline errors with descriptive message (but not stack traces in production)
- `GET /api/health` endpoint returns `{status: 'ok', version: '0.1.0'}`
- CORS middleware configured to allow localhost:3000 (Next.js dev server)
- Application factory:
  - `cantena/api/app.py` has `create_app(anthropic_api_key: str | None = None)` that wires up dependencies
  - If no key provided, reads from `ANTHROPIC_API_KEY` env var
- `cantena/api/deps.py` handles dependency injection: creates `PdfProcessor`, `VlmAnalyzer`, `CostEngine` instances
- Tests in `tests/test_api.py` using FastAPI TestClient:
  1. Health endpoint returns 200
  2. Analyze endpoint with a test PDF returns 200 with valid CostEstimate JSON (mock VLM)
  3. Non-PDF file returns 400
  4. Missing fields return 422
  5. Pipeline error returns 500 with error message
- Add fastapi, uvicorn, python-multipart to `pyproject.toml`
- `mypy --strict` passes

- **Passes:** false
- **Notes:**  
  The create_app factory pattern is important — it allows tests to inject mocked dependencies without env vars. FastAPI's dependency injection plays well with this. Keep the API surface minimal for MVP: one endpoint that does everything. We can add separate endpoints for 'just analyze the drawing' vs 'just estimate from parameters' later. The summary_dict/export_dict from PRD 1 US-008 are included in the response so the frontend doesn't have to reformat.

---

### US-106 — Upload UI: PDF upload with location input

- **Category:** core
- **Title:** Upload UI: PDF upload with location input
- **Description:**  
  As a PM trying the demo, I want to upload a floor plan PDF and enter a project location so that the system can analyze my drawing.

#### Acceptance criteria

- `frontend/app/page.tsx` is the main page with upload interface
- UI has:
  - (a) drag-and-drop zone for PDF upload (also click-to-browse)
  - (b) project name text input
  - (c) city text input
  - (d) state dropdown with US states
  - (e) 'Analyze' button
- File validation:
  - only accepts .pdf files
  - max 50MB
  - shows error for invalid files
- Loading state:
  - when analyzing, show a progress indicator with stages ('Processing PDF...', 'Analyzing drawing...', 'Generating estimate...')
- Error state:
  - if API returns an error, show descriptive message with option to retry
- On successful response, navigates to or renders the results view (can be same page, scrolling down)
- Responsive design that works on desktop (primarily) and tablet
- Uses the api.ts fetch wrapper from US-101
- Clean, professional design — this is for construction PMs, not developers. Think 'simple enterprise tool', not 'flashy startup'. Muted blues and grays, clear typography, generous whitespace
- `npm run typecheck` and `npm run lint` pass

- **Passes:** false
- **Notes:**  
  The loading states are important for the demo. Processing takes 15-30 seconds, and construction PMs are not used to waiting for software. The staged progress messages ('Analyzing drawing...') build anticipation and trust. Keep the form simple — project name + location + file is all we need. Don't add fields the VLM will extract (building type, SF, etc.) — that's the whole point.

---

### US-107 — Results UI: budget display with division breakdown

- **Category:** core
- **Title:** Results UI: budget display with division breakdown
- **Description:**  
  As a PM reviewing an estimate, I want to see the conceptual budget with a clear breakdown by CSI division so that I can quickly assess whether the numbers make sense.

#### Acceptance criteria

- Results section shows after successful analysis, on the same page below the upload form
- Header section:
  - project name
  - building summary (type, SF, stories, structure, wall system, location)
  - total cost (expected value prominently, range in smaller text)
  - cost per SF (expected, range)
- Division breakdown table:
  - CSI division number
  - division name
  - expected cost (formatted)
  - percent of total
  - cost range
  - Sorted by cost descending (biggest cost drivers first)
  - Top 3 rows visually highlighted
- Assumptions section:
  - collapsible panel listing every assumption the system made
  - parameter name, assumed value, reasoning, confidence level
  - confidence shown as colored badge (green=HIGH, yellow=MEDIUM, red=LOW)
- AI reasoning section:
  - collapsible panel showing what the VLM observed in the drawing (the 'reasoning' field from VlmAnalysisResult)
  - This is the 'show your work' that builds trust
- Metadata footer:
  - timestamp
  - engine version
  - estimation method
  - location factor applied
- All monetary values use the formatting from PRD 1 (millions for large numbers, cost/SF as range)
- `npm run typecheck` and `npm run lint` pass

- **Passes:** false
- **Notes:**  
  The division breakdown is what PMs know and expect. CSI MasterFormat is universal in US commercial construction. Showing divisions sorted by cost (not by division number) helps PMs instantly see what drives the budget. The assumptions panel is THE trust builder — Gunnar said 'I need to understand the material' and 'don't make estimators dumber'. Every assumption being visible means the PM learns from the tool. The AI reasoning section lets them verify the VLM didn't hallucinate ('it says steel frame, but I know this is concrete').

---

### US-108 — Parameter override: let PM correct extracted values

- **Category:** integration
- **Title:** Parameter override: let PM correct extracted values
- **Description:**  
  As a PM, I want to correct any parameter the AI extracted from my drawing so that I can fix mistakes and see the budget update immediately.

#### Acceptance criteria

- Building parameters section between the header and division breakdown shows each extracted parameter as an editable field
- Editable fields:
  - building type (dropdown)
  - gross SF (number input)
  - stories (number input)
  - story height (number input)
  - structural system (dropdown)
  - exterior wall (dropdown)
  - location city/state (text/dropdown)
- Each field shows the confidence badge from the VLM analysis (HIGH/MEDIUM/LOW)
- When user changes any parameter, a 'Recalculate' button appears (not auto-submit — PMs want to review changes before recalculating)
- Recalculate sends the corrected BuildingModel directly to a `POST /api/estimate` endpoint (bypasses VLM, goes straight to cost engine)
- Backend: `POST /api/estimate` endpoint accepts a BuildingModel JSON body and returns a CostEstimate (no PDF, no VLM — just the cost engine)
- Budget display updates with new estimate after recalculation
- Original estimate is preserved — user can toggle between 'AI estimate' and 'adjusted estimate' or see them side by side
- `npm run typecheck` and `npm run lint` pass
- Backend tests:
  - `/api/estimate` endpoint with valid BuildingModel returns 200
  - with invalid data returns 422

- **Passes:** false
- **Notes:**  
  This is the 'human-in-the-loop' feature Gunnar described. The AI gives you a starting point, you refine it. The `/api/estimate` endpoint is also useful as a standalone tool — a PM who already knows their building parameters can skip the VLM entirely and just get a budget. This is the 'graceful degradation' for when drawings are too rough for VLM analysis. The deliberate 'Recalculate' button (vs auto-update) is because construction PMs want control. They don't trust magic.

---

### US-109 — Docker Compose for local development

- **Category:** integration
- **Title:** Docker Compose for local development
- **Description:**  
  As a developer, I want a single command to start the full stack locally so that anyone on the team can run the complete application.

#### Acceptance criteria

- `docker-compose.yml` at project root defines two services: backend (FastAPI) and frontend (Next.js)
- Backend service:
  - builds from `backend/Dockerfile`
  - exposes port 8000
  - mounts `backend/` for hot reload
  - passes `ANTHROPIC_API_KEY` from `.env` file
- Frontend service:
  - builds from `frontend/Dockerfile`
  - exposes port 3000
  - mounts `frontend/` for hot reload
  - proxies API calls to backend
- `backend/Dockerfile`:
  - Python 3.11 slim image
  - installs dependencies from `pyproject.toml`
  - runs uvicorn with reload
- `frontend/Dockerfile`:
  - Node 20 image
  - installs dependencies
  - runs `next dev`
- `.env.example` file with `ANTHROPIC_API_KEY=your-key-here` placeholder
- `docker compose up` starts both services and they can communicate
- `README.md` at project root with:
  - project overview (one paragraph)
  - prerequisites (Docker, API key)
  - setup instructions (copy .env.example, docker compose up)
  - links to `backend/README.md` for engine details
- Quality gates still pass when run inside the backend container

- **Passes:** false
- **Notes:**  
  Docker Compose makes onboarding trivial. David and Estiven shouldn't need to figure out Python virtual environments to run the backend. The `.env.example` pattern is standard and safe. Hot reload on both services means rapid iteration during the demo sprint. Keep Dockerfiles simple — no multi-stage builds, no optimization. Working > optimized for demo stage.

---

### US-110 — Demo polish: sample results and error recovery

- **Category:** polish
- **Title:** Demo polish: sample results and error recovery
- **Description:**  
  As a developer demoing to PMs, I want sample/cached results available and graceful error handling so that the demo doesn't fail live.

#### Acceptance criteria

- `GET /api/sample-estimate` endpoint returns a pre-built CostEstimate for a realistic project (e.g., 45,000 SF 3-story steel office in Baltimore) — no VLM call needed
- Frontend has a 'Try sample estimate' link/button that loads the sample without requiring PDF upload
- If `ANTHROPIC_API_KEY` is not set, the `/api/analyze` endpoint returns a helpful error message suggesting the user try the sample estimate instead
- Frontend error boundary: if the results component crashes, shows 'Something went wrong' with retry option instead of blank screen
- Backend request timeout:
  - VLM call has a 60-second timeout
  - If exceeded, returns descriptive timeout error
- All existing tests still pass
- `npm run typecheck` and `npm run lint` pass

- **Passes:** false
- **Notes:**  
  The sample estimate is demo insurance. If the Anthropic API is slow, or the demo WiFi is bad, or the PDF is weird — you always have a working demo to show. The sample should be a realistic project that a PM would recognize: '3-story steel-frame office building, 45,000 SF, curtain wall, Baltimore MD'. This also lets people try the UI without an API key, which matters for the team during development.
