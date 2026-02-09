"""LLM-as-Judge graded tests for first-floor.pdf pipeline output.

Uses a session-scoped ``grade_card`` fixture (1 grading API call) to evaluate
the full pipeline holistically.  Each test asserts a minimum threshold on a
specific dimension, catching regressions without brittle hard-coded assertions.

Skipped gracefully when ANTHROPIC_API_KEY is not set or on 429 rate-limit.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.integration.llm_grader import GradeCard

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOverallGrade:
    """Overall weighted score must meet the passing threshold (0.70)."""

    def test_overall_grade_passes(self, grade_card: GradeCard) -> None:
        print(f"\n  Overall score: {grade_card.overall_score:.2f}")
        print(f"  Passing: {grade_card.passing}")
        assert grade_card.passing, (
            f"Overall grade {grade_card.overall_score:.2f} is below 0.70"
        )


class TestBuildingTypeGrade:
    """Building type identification should score >= 0.8."""

    def test_building_type_grade(self, grade_card: GradeCard) -> None:
        score = grade_card.building_type_score
        print(f"\n  Building type score: {score:.2f}")
        if "building_type" in grade_card.reasoning:
            print(f"  Reasoning: {grade_card.reasoning['building_type']}")
        assert score >= 0.8, (
            f"Building type score {score:.2f} is below 0.8"
        )


class TestRoomCompletenessGrade:
    """Room completeness should score >= 0.6."""

    def test_room_completeness_grade(self, grade_card: GradeCard) -> None:
        score = grade_card.room_completeness_score
        print(f"\n  Room completeness score: {score:.2f}")
        if "room_completeness" in grade_card.reasoning:
            print(
                f"  Reasoning: {grade_card.reasoning['room_completeness']}"
            )
        assert score >= 0.6, (
            f"Room completeness score {score:.2f} is below 0.6"
        )


class TestRoomClassificationGrade:
    """Room classification should score >= 0.6."""

    def test_room_classification_grade(self, grade_card: GradeCard) -> None:
        score = grade_card.room_classification_score
        print(f"\n  Room classification score: {score:.2f}")
        if "room_classification" in grade_card.reasoning:
            print(
                f"  Reasoning:"
                f" {grade_card.reasoning['room_classification']}"
            )
        assert score >= 0.6, (
            f"Room classification score {score:.2f} is below 0.6"
        )


class TestAreaReasonablenessGrade:
    """Area reasonableness should score >= 0.5."""

    def test_area_reasonableness_grade(self, grade_card: GradeCard) -> None:
        score = grade_card.area_reasonableness_score
        print(f"\n  Area reasonableness score: {score:.2f}")
        if "area_reasonableness" in grade_card.reasoning:
            print(
                f"  Reasoning:"
                f" {grade_card.reasoning['area_reasonableness']}"
            )
        assert score >= 0.5, (
            f"Area reasonableness score {score:.2f} is below 0.5"
        )


class TestNoHallucinationsGrade:
    """No hallucinations should score >= 0.7."""

    def test_no_hallucinations_grade(self, grade_card: GradeCard) -> None:
        score = grade_card.no_hallucinations_score
        print(f"\n  No hallucinations score: {score:.2f}")
        if "no_hallucinations" in grade_card.reasoning:
            print(
                f"  Reasoning:"
                f" {grade_card.reasoning['no_hallucinations']}"
            )
        assert score >= 0.7, (
            f"No hallucinations score {score:.2f} is below 0.7"
        )


class TestGradeCardReport:
    """Write the full grade card report to stdout and test_results/."""

    def test_grade_card_report(self, grade_card: GradeCard) -> None:
        report = grade_card.to_markdown()
        print(f"\n{report}")

        # Write report to test_results/
        project_root = Path(__file__).resolve().parents[3]
        report_dir = project_root / "test_results"
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / "first-floor-grade-report.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"\n  Report written to: {report_path}")
