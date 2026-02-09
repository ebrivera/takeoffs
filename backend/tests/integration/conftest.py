"""Shared fixtures for integration tests against real architectural drawings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import fitz  # type: ignore[import-untyped]
import pytest
from dotenv import load_dotenv

if TYPE_CHECKING:
    from collections.abc import Generator

    from cantena.geometry.measurement import PageMeasurements
    from tests.integration.llm_grader import GradeCard

# ---------------------------------------------------------------------------
# Load .env so ANTHROPIC_API_KEY is available (mirrors app.py)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _PROJECT_ROOT / "backend"
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_BACKEND_DIR / ".env")

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_TEST_PDF_DIR = _PROJECT_ROOT / "test_pdfs"
FIRST_FLOOR_PDF = _TEST_PDF_DIR / "first-floor.pdf"

# ---------------------------------------------------------------------------
# Ground truth values for first-floor.pdf (American Farmhouse 1st Floor)
# Scale: 1/4" = 1'-0"  →  scale_factor = 48.0
# Main building footprint: 32' × 16' = 512 SF
# ---------------------------------------------------------------------------

EXPECTED_SCALE_FACTOR = 48.0
EXPECTED_OVERALL_WIDTH_FT = 32.0
EXPECTED_OVERALL_DEPTH_FT = 16.0
EXPECTED_GROSS_AREA_SF = 512.0
# Porches extend beyond main footprint; approximate total with porches
EXPECTED_TOTAL_WITH_PORCHES_SF = 700.0
EXPECTED_ROOM_COUNT = 7  # minimum: at least 7 named rooms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def first_floor_pdf() -> Generator[fitz.Document, None, None]:
    """Open test_pdfs/first-floor.pdf and yield the fitz.Document."""
    assert FIRST_FLOOR_PDF.exists(), (
        f"Test PDF not found: {FIRST_FLOOR_PDF}"
    )
    doc: fitz.Document = fitz.open(str(FIRST_FLOOR_PDF))
    yield doc
    doc.close()


@pytest.fixture()
def first_floor_page(
    first_floor_pdf: fitz.Document,
) -> fitz.Page:
    """Yield the first (and only) page of first-floor.pdf."""
    assert len(first_floor_pdf) >= 1, "PDF has no pages"
    return first_floor_pdf[0]


# ---------------------------------------------------------------------------
# Session-scoped LLM fixture (one API call shared across all LLM e2e tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def llm_page_measurements() -> PageMeasurements:
    """Full pipeline result with LLM enrichment (1 API call, shared).

    Skips the entire session if ANTHROPIC_API_KEY is not set or if the
    API returns a 429 rate-limit error.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    from cantena.geometry.extractor import VectorExtractor
    from cantena.geometry.measurement import MeasurementService
    from cantena.geometry.scale import ScaleDetector
    from cantena.geometry.scale_verify import ScaleVerifier
    from cantena.geometry.walls import WallDetector
    from cantena.services.llm_geometry_interpreter import LlmGeometryInterpreter

    assert FIRST_FLOOR_PDF.exists(), f"Test PDF not found: {FIRST_FLOOR_PDF}"

    service = MeasurementService(
        extractor=VectorExtractor(),
        scale_detector=ScaleDetector(),
        wall_detector=WallDetector(),
        llm_interpreter=LlmGeometryInterpreter(api_key=api_key),
        scale_verifier=ScaleVerifier(api_key=api_key),
    )

    doc: fitz.Document = fitz.open(str(FIRST_FLOOR_PDF))
    try:
        page = doc[0]
        try:
            result = service.measure(page)
        except Exception as exc:
            if "429" in str(exc):
                pytest.skip("Rate limited (429)")
            raise
    finally:
        doc.close()

    return result


# ---------------------------------------------------------------------------
# Session-scoped grading fixture (1 grading API call shared across tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def grade_card(llm_page_measurements: PageMeasurements) -> GradeCard:
    """Grade the full pipeline output via an LLM-as-Judge call.

    Depends on ``llm_page_measurements`` (1 pipeline API call) and adds
    1 grading API call.  All grading tests share this single result.

    Skips gracefully on missing key or 429.
    """
    from cantena.models.building import BuildingModel, ComplexityScores, Location
    from cantena.models.enums import (
        BuildingType,
        Confidence,
        ExteriorWall,
        MechanicalSystem,
        StructuralSystem,
    )
    from cantena.services.space_assembler import SpaceAssembler
    from tests.integration.llm_grader import (
        FIRST_FLOOR_GROUND_TRUTH,
        PipelineGrader,
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    result = llm_page_measurements

    # Build a BuildingModel matching the farmhouse
    building = BuildingModel(
        building_type=BuildingType.APARTMENT_LOW_RISE,
        building_use="Single-family residential",
        gross_sf=result.gross_area_sf or 512.0,
        stories=1,
        story_height_ft=9.0,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall_system=ExteriorWall.WOOD_SIDING,
        mechanical_system=MechanicalSystem.SPLIT_SYSTEM,
        location=Location(city="Rural", state="VA"),
        complexity_scores=ComplexityScores(
            structural=2, mep=2, finishes=2, site=1,
        ),
        confidence={
            "building_type": Confidence.MEDIUM,
            "gross_sf": Confidence.HIGH,
        },
    )

    assembler = SpaceAssembler()
    program = assembler.assemble(result, building)

    grader = PipelineGrader(api_key=api_key)
    try:
        return grader.grade(result, program, FIRST_FLOOR_GROUND_TRUTH)
    except Exception as exc:
        if "429" in str(exc):
            pytest.skip("Rate limited (429)")
        raise
