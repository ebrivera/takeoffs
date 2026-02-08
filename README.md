# Cantena Takeoffs

AI-powered construction cost estimation. Upload a floor plan PDF, get a conceptual budget in under 60 seconds.

**Pipeline:** PDF &rarr; high-res images &rarr; VLM analysis &rarr; BuildingModel &rarr; CostEngine &rarr; CostEstimate &rarr; UI

## Prerequisites

- Docker and Docker Compose
- (Optional) An [Anthropic API key](https://console.anthropic.com/) for VLM-based drawing analysis

## Quick Start

```bash
# 1. Clone and enter the project
cd takeoffs

# 2. Copy env file and add your API key (optional)
cp .env.example .env

# 3. Start both services
docker compose up

# 4. Open the app
open http://localhost:3000/analyze
```

The app runs on:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000

No API key? Click **Try sample estimate** on the analyze page to see a demo.

## Development (without Docker)

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the server
uvicorn cantena.api.app:create_app --factory --reload

# Quality gates
pytest
mypy --strict cantena
ruff check cantena tests
```

### Frontend

```bash
cd frontend
npm install
npm run dev

# Quality gates
npm run typecheck
npm run lint
```

## Architecture

```
backend/
  cantena/
    api/          # FastAPI endpoints
    data/         # Cost data, CSI divisions, city indexes
    models/       # Pydantic domain models
    services/     # PDF processor, VLM analyzer, pipeline
    engine.py     # CostEngine: BuildingModel -> CostEstimate
    factory.py    # create_default_engine()
  tests/          # pytest test suite

frontend/
  src/
    app/analyze/  # Upload + results UI
    lib/          # Types, API client
```
