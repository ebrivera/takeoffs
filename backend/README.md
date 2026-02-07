# Cantena Cost Engine

A standalone, well-tested Python library that takes a `BuildingModel` and produces a `CostEstimate` broken down by CSI division with confidence ranges.

## Project Structure

```
backend/
  cantena/          # Source package
    __init__.py     # Package root and public API
    py.typed        # PEP 561 marker for type checking
  tests/            # Test suite
    test_smoke.py   # Smoke tests
  pyproject.toml    # Project configuration
  README.md         # This file
```

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Quality Checks

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=cantena

# Type checking
mypy --strict cantena

# Linting
ruff check cantena tests
```

## Requirements

- Python 3.11+
- pydantic v2 (runtime validation, serialization, schema generation)
