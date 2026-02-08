"""Tests for room label matching in cantena.geometry.rooms."""

from __future__ import annotations

import math

from cantena.geometry.extractor import BoundingRect, Point2D
from cantena.geometry.rooms import RoomDetector
from cantena.geometry.scale import TextBlock
from cantena.geometry.walls import Orientation, WallSegment


def _seg(
    start: tuple[float, float],
    end: tuple[float, float],
    thickness: float | None = None,
) -> WallSegment:
    """Create a WallSegment helper for tests."""
    sx, sy = start
    ex, ey = end
    length = math.hypot(ex - sx, ey - sy)
    dx = abs(ex - sx)
    dy = abs(ey - sy)
    angle = math.degrees(math.atan2(dy, dx)) if (dx or dy) else 0.0
    if angle <= 2.0:
        orientation = Orientation.HORIZONTAL
    elif angle >= 88.0:
        orientation = Orientation.VERTICAL
    else:
        orientation = Orientation.ANGLED
    return WallSegment(
        start=Point2D(sx, sy),
        end=Point2D(ex, ey),
        thickness_pts=thickness,
        orientation=orientation,
        length_pts=length,
    )


def _text_block(text: str, x: float, y: float) -> TextBlock:
    """Create a TextBlock at position (x, y)."""
    return TextBlock(
        text=text,
        position=Point2D(x, y),
        bounding_rect=BoundingRect(x - 10, y - 5, 20, 10),
    )


def _two_room_segments() -> list[WallSegment]:
    """Two adjacent rooms: left (100,100)-(300,250), right (300,100)-(500,250)."""
    return [
        _seg((100, 100), (300, 100)),   # bottom left
        _seg((100, 100), (100, 250)),   # left wall
        _seg((100, 250), (300, 250)),   # top left
        _seg((300, 100), (300, 250)),   # shared middle wall
        _seg((300, 100), (500, 100)),   # bottom right
        _seg((500, 100), (500, 250)),   # right wall
        _seg((500, 250), (300, 250)),   # top right
    ]


class TestLabelInsidePolygon:
    """Labels inside a room polygon should be assigned to that room."""

    def test_label_assigned_to_containing_room(self) -> None:
        detector = RoomDetector()
        segs = _two_room_segments()
        analysis = detector.detect_rooms(segs)
        assert analysis.room_count == 2

        # Place "KITCHEN" inside the left room, "DINING" inside right room.
        text_blocks = [
            _text_block("KITCHEN", 200, 175),
            _text_block("DINING", 400, 175),
        ]
        result = detector.label_rooms(analysis, text_blocks)

        labels = {r.label for r in result.rooms}
        assert "KITCHEN" in labels
        assert "DINING" in labels


class TestLabelOutsideAssignsNearest:
    """Labels outside all rooms should be assigned to the nearest centroid."""

    def test_outside_label_assigned_to_nearest(self) -> None:
        """Use a small room so label outside is still within 50pts of centroid."""
        detector = RoomDetector()
        # Small room: (100,100)-(160,150) — centroid ~(130, 125)
        segs = [
            _seg((100, 100), (160, 100)),
            _seg((160, 100), (160, 150)),
            _seg((160, 150), (100, 150)),
            _seg((100, 150), (100, 100)),
        ]
        analysis = detector.detect_rooms(segs)
        assert analysis.room_count == 1

        # Label at (130, 160) — 10pts outside top wall, ~35pts from centroid
        text_blocks = [
            _text_block("KITCHEN", 130, 160),
        ]
        result = detector.label_rooms(analysis, text_blocks)

        labeled = [r for r in result.rooms if r.label is not None]
        assert len(labeled) == 1
        assert labeled[0].label == "KITCHEN"


class TestNonRoomTextIgnored:
    """Text that doesn't match known room names should be ignored."""

    def test_non_room_text_not_assigned(self) -> None:
        detector = RoomDetector()
        segs = _two_room_segments()
        analysis = detector.detect_rooms(segs)

        # Non-room text inside rooms
        text_blocks = [
            _text_block("SCALE: 1/4\"=1'-0\"", 200, 175),
            _text_block("32'-0\"", 400, 175),
            _text_block("AMERICAN FARMHOUSE", 200, 175),
        ]
        result = detector.label_rooms(analysis, text_blocks)

        labeled = [r for r in result.rooms if r.label is not None]
        assert len(labeled) == 0


class TestUnlabeledRoomsRemainNone:
    """Rooms without matching labels should keep label=None."""

    def test_unlabeled_rooms_stay_none(self) -> None:
        detector = RoomDetector()
        segs = _two_room_segments()
        analysis = detector.detect_rooms(segs)

        # Only label one room
        text_blocks = [
            _text_block("KITCHEN", 200, 175),
        ]
        result = detector.label_rooms(analysis, text_blocks)

        labels = [r.label for r in result.rooms]
        assert "KITCHEN" in labels
        assert None in labels


class TestDuplicateNamesGetIndexed:
    """Duplicate room labels should get an index suffix."""

    def test_duplicate_bedroom_labels(self) -> None:
        detector = RoomDetector()
        segs = _two_room_segments()
        analysis = detector.detect_rooms(segs)

        # Two "BEDROOM" labels in different rooms
        text_blocks = [
            _text_block("BEDROOM", 200, 175),
            _text_block("BEDROOM", 400, 175),
        ]
        result = detector.label_rooms(analysis, text_blocks)

        labels = sorted(r.label for r in result.rooms if r.label is not None)
        assert labels == ["BEDROOM 1", "BEDROOM 2"]


class TestCaseInsensitiveMatching:
    """Room name matching should be case-insensitive."""

    def test_lowercase_matches(self) -> None:
        detector = RoomDetector()
        segs = _two_room_segments()
        analysis = detector.detect_rooms(segs)

        text_blocks = [
            _text_block("living room", 200, 175),
        ]
        result = detector.label_rooms(analysis, text_blocks)

        labeled = [r for r in result.rooms if r.label is not None]
        assert len(labeled) == 1
        assert labeled[0].label == "LIVING ROOM"


class TestEmptyInputs:
    """Edge cases with empty rooms or text blocks."""

    def test_no_text_blocks(self) -> None:
        detector = RoomDetector()
        segs = _two_room_segments()
        analysis = detector.detect_rooms(segs)

        result = detector.label_rooms(analysis, [])
        assert result == analysis

    def test_no_rooms(self) -> None:
        detector = RoomDetector()
        empty = detector.detect_rooms([])

        text_blocks = [_text_block("KITCHEN", 200, 175)]
        result = detector.label_rooms(empty, text_blocks)
        assert result == empty


class TestSubstringMatch:
    """Room names embedded in longer text should still match."""

    def test_label_with_extra_whitespace(self) -> None:
        detector = RoomDetector()
        segs = _two_room_segments()
        analysis = detector.detect_rooms(segs)

        # Simulates newline-split text from PDF
        text_blocks = [
            _text_block("LIVING\nROOM", 200, 175),
        ]
        result = detector.label_rooms(analysis, text_blocks)

        labeled = [r for r in result.rooms if r.label is not None]
        assert len(labeled) == 1
        assert labeled[0].label == "LIVING ROOM"
