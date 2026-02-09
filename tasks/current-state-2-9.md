# Cantena — Current Project State (consolidated, post-execution)

## What the system does

Cantena is now a working **drawing → budget** product pipeline: a user uploads a construction plan PDF and a project location, and the system returns a conceptual cost estimate (with range + trade/CSI breakdown) in a single request/response loop.

**Core flow:**  
`PDF → images/text → (VLM + geometry) → BuildingModel → CostEngine → CostEstimate → UI`  
_Source: prd-product-pipeline_

---

## End-to-end data flow (how a request is processed)

### 1) PDF ingestion & rendering

- The PDF is converted to high-res page images and text is extracted alongside (including title-block-focused text when available), producing a structured processing result per page.  
  _Source: prd-product-pipeline_

### 2) Page selection (MVP heuristic)

- The pipeline selects the best page to analyze (MVP: first/most-likely floor plan page via simple heuristics), then runs downstream analysis on that page.  
  _Source: prd-product-pipeline_

### 3) Geometry measurement (vector PDFs)

- For CAD-exported vector PDFs, the geometry engine extracts vector paths directly (not pixels), detects scale, and computes measurements (areas/perimeters/wall lengths), replacing “square footage guessing” with computed quantities.  
  _Source: prd-geometry-engine_

### 4) Room reconstruction + labeling (accuracy upgrades)

- Wall endpoints are snapped to close tiny gaps.
- Shapely `polygonize()` reconstructs enclosed room polygons.
- Room labels are spatially matched from text blocks when possible.  
  _Source: prd-testing-llm-enhanced-geometry_

### 5) LLM enhancements (optional, not a dependency)

- An LLM interpreter can enrich/validate geometry + text into a richer semantic understanding.
- A scale “safety rail” can verify/recover scale to avoid catastrophic mis-scaling (scale² effect).
- All LLM integration is opt-in (skipped without `ANTHROPIC_API_KEY`).  
  _Source: prd-testing-llm-enhanced-geometry_

### 6) Cost estimation (domain core)

- The CostEngine takes a validated `BuildingModel` and computes:  
   `base $/SF lookup → location factor → complexity multipliers → total cost + conceptual range → CSI division breakdown → assumptions and confidence notes`  
  _Source: prd-cost-engine_

### 7) Room-aware pricing (enhanced cost intelligence)

- When room polygons + labels are available, Cantena can price each room at room-type-specific rates (e.g., kitchen vs living room) instead of a single building-wide $/SF.  
  _Source: prd-enhanced-cost-intelligence_

### 8) API + UI

- Backend exposes:
  - `POST /api/analyze` (multipart upload + location fields) returning a full `CostEstimate` JSON
  - `GET /api/health`
- Frontend provides a dedicated `/analyze` product route (landing page remains `/`).  
  _Source: prd-product-pipeline_

---

## What exists in the repo now (capabilities by subsystem)

### 1) Cost engine (domain core)

- **Typed domain models (Pydantic v2)** representing the input contract the AI/geometry produce:
  - building type/use, gross SF, stories, systems, location, complexity scores, special conditions, and confidence per field  
    _Source: prd-cost-engine_
- **Cost data repository abstraction** with:
  - square-foot cost entries + fuzzy matching fallbacks
  - CSI division percentage breakdown
  - city cost index lookups (unknown city defaults to 1.0)  
    _Source: prd-cost-engine_
- **CostEngine pipeline** producing a `CostEstimate` with ranges, division breakdown, and explicit assumptions when fallbacks/low-confidence occur.  
  _Source: prd-cost-engine_

### 2) Geometry engine (vector PDF measurement)

- **Vector extraction** via PyMuPDF `page.get_drawings()` into structured path data, with stats and region filtering to separate drawing area from title block.  
  _Source: prd-geometry-engine_
- **Scale + measurement workflow** designed to compute real quantities and integrate into the product pipeline as the measurement source of truth (VLM remains semantic).  
  _Source: prd-geometry-engine_

### 3) Real-drawing validation suite (integration confidence)

- Full integration test suite against a real fixture PDF (`test_pdfs/first-floor.pdf`) with known ground truth (e.g., 32’×16’ footprint, named rooms, explicit scale). Validates vector extraction, scale, walls, measurements, and hybrid pipeline end-to-end.  
  _Source: prd-testing-geometry_
- Engineering principle enforced: **no single point of failure in parsing** — scale parsing must degrade gracefully and/or fall back rather than hard-fail.  
  _Source: prd-testing-geometry_

### 4) LLM-enhanced geometry (accuracy + safety rails)

- **Endpoint snapping** (small tolerance) to enable polygon closure.  
  _Source: prd-testing-llm-enhanced-geometry_
- **Room polygon reconstruction** via `polygonize()` with filtering + fallback behavior.  
  _Source: prd-testing-llm-enhanced-geometry_
- **LLM is an enhancement, not a dependency**; tests/run modes explicitly support skipping LLM paths when no key is set.  
  _Source: prd-testing-llm-enhanced-geometry_

### 5) Product pipeline (API + UI)

- **AnalysisPipeline** orchestrates:
  `PDF processing → page selection → VLM → cost engine → cleanup`  
  Failures are wrapped into distinct exception types for the API layer.  
  _Source: prd-product-pipeline_
- **FastAPI service** with minimal endpoints (`/api/analyze`, `/api/health`) and DI wiring designed for testability.  
  _Source: prd-product-pipeline_
- **Next.js frontend** (typed contract) with product UI on `/analyze` and upload/location inputs.  
  _Source: prd-product-pipeline_

### 6) Enhanced cost intelligence (room-aware estimating)

- **RoomType model + seed room cost data** enabling differentiated $/SF per room type and building context (res + commercial).  
  _Source: prd-enhanced-cost-intelligence_
- **Room-level pricing output** producing estimates that show per-room line items rather than only a single aggregated building rate.  
  _Source: prd-enhanced-cost-intelligence_

---

## Output contract (what the agent/UI can rely on)

- The backend returns a structured `CostEstimate` (including conceptual range, CSI/trade breakdown, and explicit assumptions).
- The API response includes formatting helpers intended for UI consumption (e.g., summary/export dictionaries).  
  _Source: prd-product-pipeline_

---

## Quality bar (what “done” means in this repo)

- Backend is consistently held to: `pytest`, coverage thresholds, `mypy --strict`, and `ruff` checks across subsystems.  
  _Source: prd-geometry-engine_
- Frontend is held to: `npm run typecheck` and `npm run lint`.  
  _Source: prd-product-pipeline_
