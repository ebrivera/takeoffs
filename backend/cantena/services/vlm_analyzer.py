"""VLM analysis service — sends construction drawing images to Anthropic Vision API."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
from anthropic.types import ImageBlockParam, TextBlockParam

from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import (
    BuildingType,
    Confidence,
    ElectricalService,
    ExteriorWall,
    FireProtection,
    MechanicalSystem,
    StructuralSystem,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models (dataclasses for internal service results)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalysisContext:
    """Optional context to guide VLM analysis."""

    project_name: str | None = None
    location: str | None = None
    additional_notes: str | None = None


@dataclass(frozen=True)
class VlmAnalysisResult:
    """Result of VLM analysis of a construction drawing."""

    building_model: BuildingModel
    raw_response: str
    reasoning: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an expert construction cost estimator analyzing a "
    "construction drawing.\n\n"
    "Your task is to extract building parameters from the drawing "
    "to enable cost estimation.\n\n"
    "Follow this multi-pass approach:\n\n"
    "**Pass 1 — Describe what you see:**\n"
    "Describe the drawing in detail. What type of building is it? "
    "How many stories? What structural system is visible? "
    "What exterior wall materials? Any MEP systems visible? "
    "What is the approximate gross square footage?\n\n"
    "**Pass 2 — State your confidence:**\n"
    "For each parameter, state whether you are HIGH, MEDIUM, or LOW "
    "confidence. HIGH means clearly visible/labeled on the drawing. "
    "MEDIUM means you can infer it with reasonable certainty. "
    "LOW means you are guessing based on building type norms.\n\n"
    "**Pass 3 — Flag guesses:**\n"
    "Explicitly list any parameters where you are making assumptions "
    "rather than reading from the drawing. These will be presented "
    "to the user for correction.\n\n"
    "**Pass 4 — Output JSON:**\n"
    "Output a JSON object matching EXACTLY this schema. "
    "Do not add or remove fields.\n\n"
    "```json\n"
    "{\n"
    '  "building_type": "<one of: apartment_low_rise, '
    "apartment_mid_rise, apartment_high_rise, office_low_rise, "
    "office_mid_rise, office_high_rise, retail, warehouse, "
    'school_elementary, school_high, hospital, hotel>",\n'
    '  "building_use": "<brief description>",\n'
    '  "gross_sf": "<number, estimated gross square footage>",\n'
    '  "stories": "<integer, number of stories>",\n'
    '  "story_height_ft": "<number, typical story height in feet>",\n'
    '  "structural_system": "<one of: wood_frame, steel_frame, '
    'concrete_frame, masonry_bearing, precast_concrete>",\n'
    '  "exterior_wall_system": "<one of: brick_veneer, curtain_wall, '
    'metal_panel, precast_panel, stucco, wood_siding, eifs>",\n'
    '  "mechanical_system": "<one of: split_system, packaged_rooftop, '
    'chilled_water, vav, vrf, or null>",\n'
    '  "electrical_service": "<one of: light, standard, heavy, '
    'or null>",\n'
    '  "fire_protection": "<one of: none, sprinkler_wet, '
    'sprinkler_combined, or null>",\n'
    '  "complexity_scores": {\n'
    '    "structural": "<1-5>",\n'
    '    "mep": "<1-5>",\n'
    '    "finishes": "<1-5>",\n'
    '    "site": "<1-5>"\n'
    "  },\n"
    '  "special_conditions": ["<list of special conditions>"],\n'
    '  "confidence": {\n'
    '    "building_type": "<high, medium, or low>",\n'
    '    "gross_sf": "<high, medium, or low>",\n'
    '    "stories": "<high, medium, or low>",\n'
    '    "structural_system": "<high, medium, or low>",\n'
    '    "exterior_wall_system": "<high, medium, or low>"\n'
    "  }\n"
    "}\n"
    "```\n\n"
    "IMPORTANT:\n"
    "- Output your reasoning FIRST, then the JSON block.\n"
    "- Wrap the JSON in ```json ... ``` code fences.\n"
    "- Every field is required. If you cannot determine a value, "
    'use your best guess and mark confidence as "low".\n'
    "- gross_sf must be > 0, stories must be >= 1, "
    "story_height_ft must be > 0.\n"
)


# ---------------------------------------------------------------------------
# VLM Analyzer
# ---------------------------------------------------------------------------

_MAX_RETRIES = 1


class VlmAnalyzer:
    """Sends construction drawing images to Anthropic Vision API for analysis."""

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

    def analyze(
        self,
        image_path: Path,
        context: AnalysisContext | None = None,
    ) -> VlmAnalysisResult:
        """Analyze a construction drawing image and return a BuildingModel.

        Parameters
        ----------
        image_path
            Path to a PNG image of a construction drawing page.
        context
            Optional context (project name, location, notes) to guide analysis.

        Raises
        ------
        ValueError
            If the image cannot be read or the VLM returns unparseable output
            after retries.
        """
        image_data = self._load_image(image_path)
        user_content = self._build_user_content(image_data, context)

        # First attempt
        raw_response = self._call_api(user_content)
        result = self._parse_response(raw_response, context)
        if result is not None:
            return result

        # Retry once on malformed response
        logger.warning("Malformed VLM response, retrying (attempt 2/%d)", _MAX_RETRIES + 1)
        raw_response = self._call_api(user_content)
        result = self._parse_response(raw_response, context)
        if result is not None:
            return result

        msg = "VLM returned unparseable response after retries"
        raise ValueError(msg)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_image(image_path: Path) -> str:
        """Load image and return base64-encoded string."""
        image_path = Path(image_path)
        if not image_path.exists():
            msg = f"Image file not found: {image_path}"
            raise ValueError(msg)
        return base64.b64encode(image_path.read_bytes()).decode("utf-8")

    @staticmethod
    def _build_user_content(
        image_data: str,
        context: AnalysisContext | None,
    ) -> list[ImageBlockParam | TextBlockParam]:
        """Build the user message content with image and optional context."""
        parts: list[ImageBlockParam | TextBlockParam] = [
            ImageBlockParam(
                type="image",
                source={
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_data,
                },
            ),
        ]

        text_parts: list[str] = [
            "Analyze this construction drawing and extract building parameters.",
        ]
        if context:
            if context.project_name:
                text_parts.append(f"Project name: {context.project_name}")
            if context.location:
                text_parts.append(f"Location: {context.location}")
            if context.additional_notes:
                text_parts.append(f"Additional notes: {context.additional_notes}")

        parts.append(TextBlockParam(type="text", text="\n".join(text_parts)))
        return parts

    def _call_api(
        self, user_content: list[ImageBlockParam | TextBlockParam]
    ) -> str:
        """Call the Anthropic Messages API with vision."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        # Extract text from the response
        text_blocks = [block.text for block in response.content if block.type == "text"]
        return "\n".join(text_blocks)

    def _parse_response(
        self,
        raw_response: str,
        context: AnalysisContext | None,
    ) -> VlmAnalysisResult | None:
        """Parse VLM response into a VlmAnalysisResult, or None if malformed."""
        json_str = self._extract_json(raw_response)
        if json_str is None:
            logger.warning("No JSON block found in VLM response")
            return None

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in VLM response")
            return None

        return self._build_result(data, raw_response, context)

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """Extract JSON from ```json ... ``` code fences."""
        start = text.find("```json")
        if start == -1:
            # Try plain ``` fences
            start = text.find("```")
            if start == -1:
                return None
            start += 3
        else:
            start += 7

        end = text.find("```", start)
        if end == -1:
            return None

        return text[start:end].strip()

    def _build_result(
        self,
        data: dict[str, Any],
        raw_response: str,
        context: AnalysisContext | None,
    ) -> VlmAnalysisResult | None:
        """Build a VlmAnalysisResult from parsed JSON data."""
        warnings: list[str] = []

        # Apply LOW confidence defaults for missing fields
        data = self._apply_defaults(data, warnings)

        # Extract reasoning (everything before the JSON block)
        reasoning = self._extract_reasoning(raw_response)

        # Build location from context or default
        location = self._build_location(context)

        try:
            building_model = BuildingModel(
                building_type=BuildingType(data["building_type"]),
                building_use=data.get("building_use", "Unknown"),
                gross_sf=float(data["gross_sf"]),
                stories=int(data["stories"]),
                story_height_ft=float(data.get("story_height_ft", 10.0)),
                structural_system=StructuralSystem(data["structural_system"]),
                exterior_wall_system=ExteriorWall(data["exterior_wall_system"]),
                mechanical_system=(
                    MechanicalSystem(data["mechanical_system"])
                    if data.get("mechanical_system")
                    else None
                ),
                electrical_service=(
                    ElectricalService(data["electrical_service"])
                    if data.get("electrical_service")
                    else None
                ),
                fire_protection=(
                    FireProtection(data["fire_protection"])
                    if data.get("fire_protection")
                    else None
                ),
                location=location,
                complexity_scores=self._parse_complexity(data.get("complexity_scores")),
                special_conditions=data.get("special_conditions", []),
                confidence=self._parse_confidence(data.get("confidence", {})),
            )
        except (ValueError, KeyError) as exc:
            logger.warning("Failed to build BuildingModel from VLM data: %s", exc)
            return None

        return VlmAnalysisResult(
            building_model=building_model,
            raw_response=raw_response,
            reasoning=reasoning,
            warnings=warnings,
        )

    @staticmethod
    def _apply_defaults(data: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
        """Fill missing fields with LOW-confidence defaults."""
        defaults: dict[str, Any] = {
            "building_type": BuildingType.OFFICE_MID_RISE.value,
            "building_use": "General commercial",
            "gross_sf": 25000.0,
            "stories": 2,
            "story_height_ft": 10.0,
            "structural_system": StructuralSystem.STEEL_FRAME.value,
            "exterior_wall_system": ExteriorWall.BRICK_VENEER.value,
        }
        confidence = data.get("confidence", {})
        for key, default in defaults.items():
            if key not in data or data[key] is None:
                data[key] = default
                warnings.append(f"Missing field '{key}' — using default: {default}")
                confidence[key] = Confidence.LOW.value
        data["confidence"] = confidence
        return data

    @staticmethod
    def _extract_reasoning(raw_response: str) -> str:
        """Extract reasoning text before the JSON block."""
        start = raw_response.find("```")
        if start == -1:
            return raw_response.strip()
        return raw_response[:start].strip()

    @staticmethod
    def _build_location(context: AnalysisContext | None) -> Location:
        """Build a Location from context or use default."""
        if context and context.location:
            # Try to parse "City, State" format
            parts = [p.strip() for p in context.location.split(",")]
            if len(parts) >= 2:
                return Location(city=parts[0], state=parts[1])
            return Location(city=context.location, state="")
        return Location(city="", state="")

    @staticmethod
    def _parse_complexity(data: dict[str, Any] | None) -> ComplexityScores:
        """Parse complexity scores from VLM output."""
        if not data:
            return ComplexityScores()
        return ComplexityScores(
            structural=int(data.get("structural", 3)),
            mep=int(data.get("mep", 3)),
            finishes=int(data.get("finishes", 3)),
            site=int(data.get("site", 3)),
        )

    @staticmethod
    def _parse_confidence(data: dict[str, Any]) -> dict[str, Confidence]:
        """Parse confidence dict, mapping string values to Confidence enum."""
        result: dict[str, Confidence] = {}
        for key, val in data.items():
            try:
                result[key] = Confidence(val)
            except ValueError:
                result[key] = Confidence.LOW
        return result
