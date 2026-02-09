"""LLM-as-Judge grading system for pipeline output validation.

Defines ground truth for known test drawings, a structured GradeCard with
per-dimension scores, and a PipelineGrader that uses a separate Claude API
call to holistically evaluate pipeline output against ground truth.

This replaces brittle hard-coded assertions with flexible, regression-catching
semantic evaluation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import anthropic

if TYPE_CHECKING:
    from cantena.geometry.measurement import PageMeasurements
    from cantena.models.space_program import SpaceProgram

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ground Truth
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroundTruth:
    """Expected characteristics of a known architectural drawing."""

    name: str
    building_type: str
    structural_system_keywords: list[str]
    total_area_sf: float
    area_tolerance_pct: float
    scale_factor: float
    expected_rooms: list[str]
    special_conditions: list[str]
    min_room_count: int


FIRST_FLOOR_GROUND_TRUTH = GroundTruth(
    name="American Farmhouse 1st Floor (first-floor.pdf)",
    building_type="RESIDENTIAL",
    structural_system_keywords=["wood", "frame", "timber"],
    total_area_sf=512.0,
    area_tolerance_pct=20.0,
    scale_factor=48.0,
    expected_rooms=[
        "Kitchen",
        "Living Room",
        "Dining",
        "WC",
        "Utility",
        "Laundry",
        "Front Porch",
        "Back Porch",
    ],
    special_conditions=["woodstove", "fireplace", "chimney", "hardwood"],
    min_room_count=6,
)


# ---------------------------------------------------------------------------
# GradeCard
# ---------------------------------------------------------------------------

_DIMENSION_WEIGHTS: dict[str, float] = {
    "building_type": 0.15,
    "structural_system": 0.10,
    "room_completeness": 0.25,
    "room_classification": 0.20,
    "area_reasonableness": 0.15,
    "special_conditions": 0.05,
    "no_hallucinations": 0.10,
}

_PASSING_THRESHOLD = 0.70


@dataclass
class GradeCard:
    """Structured per-dimension scores from the grading LLM."""

    building_type_score: float = 0.0
    structural_system_score: float = 0.0
    room_completeness_score: float = 0.0
    room_classification_score: float = 0.0
    area_reasonableness_score: float = 0.0
    special_conditions_score: float = 0.0
    no_hallucinations_score: float = 0.0
    reasoning: dict[str, str] = field(default_factory=dict)

    @property
    def overall_score(self) -> float:
        """Weighted sum of all dimension scores."""
        scores = {
            "building_type": self.building_type_score,
            "structural_system": self.structural_system_score,
            "room_completeness": self.room_completeness_score,
            "room_classification": self.room_classification_score,
            "area_reasonableness": self.area_reasonableness_score,
            "special_conditions": self.special_conditions_score,
            "no_hallucinations": self.no_hallucinations_score,
        }
        return sum(
            scores[dim] * _DIMENSION_WEIGHTS[dim] for dim in _DIMENSION_WEIGHTS
        )

    @property
    def passing(self) -> bool:
        """Whether overall score meets the passing threshold."""
        return self.overall_score >= _PASSING_THRESHOLD

    def to_markdown(self) -> str:
        """Render the grade card as a markdown report."""
        lines = [
            "# Pipeline Grade Report",
            "",
            f"**Overall Score: {self.overall_score:.2f}**"
            f" ({'PASS' if self.passing else 'FAIL'}"
            f" — threshold {_PASSING_THRESHOLD:.2f})",
            "",
            "## Dimension Scores",
            "",
            "| Dimension | Weight | Score |",
            "|-----------|--------|-------|",
        ]
        score_map = {
            "building_type": self.building_type_score,
            "structural_system": self.structural_system_score,
            "room_completeness": self.room_completeness_score,
            "room_classification": self.room_classification_score,
            "area_reasonableness": self.area_reasonableness_score,
            "special_conditions": self.special_conditions_score,
            "no_hallucinations": self.no_hallucinations_score,
        }
        for dim, weight in _DIMENSION_WEIGHTS.items():
            score = score_map[dim]
            lines.append(f"| {dim} | {weight:.2f} | {score:.2f} |")

        if self.reasoning:
            lines.extend(["", "## Reasoning", ""])
            for dim, text in self.reasoning.items():
                lines.append(f"**{dim}**: {text}")
                lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Grading system prompt
# ---------------------------------------------------------------------------

_GRADING_SYSTEM_PROMPT = """\
You are an expert evaluator grading the output of an architectural floor plan \
analysis pipeline.  You will receive:
1. The pipeline's output (detected rooms, building type, areas, etc.)
2. The ground truth for the drawing being analyzed.

Score each of the following 7 dimensions from 0.0 to 1.0, and provide brief \
reasoning for each score.

Dimensions:
- building_type: Did the pipeline correctly identify the building type?
- structural_system: Did the pipeline identify the structural system (e.g. \
wood frame)?
- room_completeness: Did the pipeline find all expected rooms? Partial credit \
for finding most.
- room_classification: Are room types correctly assigned (Kitchen=kitchen, \
not bedroom, etc.)?
- area_reasonableness: Are total and per-room areas physically reasonable \
given the building?
- special_conditions: Were notable features (woodstove, chimney, hardwood, \
etc.) identified?
- no_hallucinations: No phantom rooms, impossible areas, or fabricated claims?

Output ONLY a JSON object inside ```json ... ``` fences matching this schema:

```json
{
  "building_type_score": <float 0.0-1.0>,
  "structural_system_score": <float 0.0-1.0>,
  "room_completeness_score": <float 0.0-1.0>,
  "room_classification_score": <float 0.0-1.0>,
  "area_reasonableness_score": <float 0.0-1.0>,
  "special_conditions_score": <float 0.0-1.0>,
  "no_hallucinations_score": <float 0.0-1.0>,
  "reasoning": {
    "building_type": "<brief explanation>",
    "structural_system": "<brief explanation>",
    "room_completeness": "<brief explanation>",
    "room_classification": "<brief explanation>",
    "area_reasonableness": "<brief explanation>",
    "special_conditions": "<brief explanation>",
    "no_hallucinations": "<brief explanation>"
  }
}
```

IMPORTANT:
- Output ONLY the JSON block wrapped in ```json ... ``` fences.
- All scores must be between 0.0 and 1.0 inclusive.
- Every field is required.
"""


# ---------------------------------------------------------------------------
# PipelineGrader
# ---------------------------------------------------------------------------


class PipelineGrader:
    """Grades pipeline output against ground truth using a separate LLM call."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        timeout: float = 60.0,
    ) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout,
        )
        self._model = model

    def grade(
        self,
        page_measurements: PageMeasurements,
        space_program: SpaceProgram,
        ground_truth: GroundTruth,
    ) -> GradeCard:
        """Grade pipeline output and return a structured GradeCard.

        Never raises — returns a zero-score card on any failure.
        """
        try:
            output_text = self._serialize_output(
                page_measurements, space_program
            )
            gt_text = self._serialize_ground_truth(ground_truth)
            prompt = self._build_grading_prompt(output_text, gt_text)

            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=_GRADING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = "\n".join(
                block.text
                for block in response.content
                if block.type == "text"
            )
            card = self._parse_grade_card(raw)
            if card is not None:
                return card

            logger.warning("Could not parse grading LLM response")
            return GradeCard()

        except Exception:
            logger.exception("Pipeline grading failed")
            return GradeCard()

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_output(
        page_measurements: PageMeasurements,
        space_program: SpaceProgram,
    ) -> str:
        """Serialize pipeline output into a structured text summary."""
        lines = ["## Pipeline Output\n"]

        # Measurements summary
        lines.append(f"Gross area (SF): {page_measurements.gross_area_sf}")
        lines.append(f"Wall count: {page_measurements.wall_count}")
        lines.append(f"Confidence: {page_measurements.confidence}")
        lines.append(
            f"Polygonize success: {page_measurements.polygonize_success}"
        )

        if page_measurements.scale is not None:
            lines.append(
                f"Scale: {page_measurements.scale.notation}"
                f" (factor={page_measurements.scale.scale_factor})"
            )

        # Geometry rooms
        rooms = page_measurements.rooms or []
        lines.append(f"\n### Geometry Rooms ({len(rooms)})\n")
        for r in rooms:
            label = r.label or "(unlabeled)"
            area = f"{r.area_sf:.1f} SF" if r.area_sf else "N/A"
            lines.append(f"- [{r.room_index}] {label} — {area}")

        # LLM interpretation
        interp = page_measurements.llm_interpretation
        if interp is not None:
            lines.append("\n### LLM Interpretation\n")
            lines.append(f"Building type: {interp.building_type}")
            lines.append(f"Structural system: {interp.structural_system}")
            lines.append(
                f"Special conditions: {', '.join(interp.special_conditions)}"
            )

            lines.append(f"\n#### LLM Rooms ({len(interp.rooms)})\n")
            for r in interp.rooms:
                lines.append(
                    f"- [{r.room_index}] {r.confirmed_label}"
                    f" ({r.room_type_enum}) — {r.notes}"
                )

        # SpaceProgram
        lines.append(f"\n### Space Program ({len(space_program.spaces)} spaces"
                      f", {space_program.total_area_sf:.1f} SF total)\n")
        for s in space_program.spaces:
            lines.append(
                f"- {s.name} ({s.room_type.value}) —"
                f" {s.area_sf:.1f} SF [{s.source.value}]"
            )

        return "\n".join(lines)

    @staticmethod
    def _serialize_ground_truth(ground_truth: GroundTruth) -> str:
        """Serialize ground truth into a structured text summary."""
        lines = [
            f"## Ground Truth: {ground_truth.name}\n",
            f"Building type: {ground_truth.building_type}",
            f"Structural system keywords:"
            f" {', '.join(ground_truth.structural_system_keywords)}",
            f"Total area (SF): {ground_truth.total_area_sf}"
            f" (±{ground_truth.area_tolerance_pct}%)",
            f"Scale factor: {ground_truth.scale_factor}",
            f"Min room count: {ground_truth.min_room_count}",
            f"\nExpected rooms: {', '.join(ground_truth.expected_rooms)}",
            f"Special conditions:"
            f" {', '.join(ground_truth.special_conditions)}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_grading_prompt(output_text: str, gt_text: str) -> str:
        """Combine pipeline output and ground truth into a grading prompt."""
        return (
            f"Please grade the following pipeline output against the ground"
            f" truth.\n\n{gt_text}\n\n---\n\n{output_text}"
        )

    @staticmethod
    def _parse_grade_card(raw_response: str) -> GradeCard | None:
        """Parse the grading LLM response into a GradeCard."""
        # Extract JSON from ```json ... ``` fences
        start = raw_response.find("```json")
        if start == -1:
            start = raw_response.find("```")
            if start == -1:
                return None
            start += 3
        else:
            start += 7

        end = raw_response.find("```", start)
        if end == -1:
            return None

        json_str = raw_response[start:end].strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return None

        def _clamp(val: object) -> float:
            try:
                f = float(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return 0.0
            return max(0.0, min(1.0, f))

        reasoning_raw = data.get("reasoning", {})
        reasoning: dict[str, str] = {}
        if isinstance(reasoning_raw, dict):
            reasoning = {str(k): str(v) for k, v in reasoning_raw.items()}

        return GradeCard(
            building_type_score=_clamp(data.get("building_type_score")),
            structural_system_score=_clamp(
                data.get("structural_system_score")
            ),
            room_completeness_score=_clamp(
                data.get("room_completeness_score")
            ),
            room_classification_score=_clamp(
                data.get("room_classification_score")
            ),
            area_reasonableness_score=_clamp(
                data.get("area_reasonableness_score")
            ),
            special_conditions_score=_clamp(
                data.get("special_conditions_score")
            ),
            no_hallucinations_score=_clamp(
                data.get("no_hallucinations_score")
            ),
            reasoning=reasoning,
        )
