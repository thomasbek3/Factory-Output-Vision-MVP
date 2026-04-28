from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

Point = tuple[float, float]
Box = tuple[float, float, float, float]
Polygon = Union[list[Point], tuple[Point, ...]]


@dataclass(frozen=True)
class CalibrationZones:
    source_polygons: list[Polygon] = field(default_factory=list)
    output_polygons: list[Polygon] = field(default_factory=list)
    ignore_polygons: list[Polygon] = field(default_factory=list)


@dataclass(frozen=True)
class ZoneMembership:
    source_overlap: float
    output_overlap: float
    ignore_overlap: float
    center_in_source: bool
    center_in_output: bool
    center_in_ignore: bool


@dataclass(frozen=True)
class Gate:
    start: Point
    end: Point
    source_side: int = 1


def box_center(box: Box) -> Point:
    x, y, width, height = box
    return (x + width / 2.0, y + height / 2.0)


def box_area(box: Box) -> float:
    _, _, width, height = box
    return max(0.0, width) * max(0.0, height)


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Return True when point is inside or on the edge of a polygon."""
    x, y = point
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if _point_on_segment(point, (xi, yi), (xj, yj)):
            return True
        intersects = (yi > y) != (yj > y)
        if intersects:
            x_at_y = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x <= x_at_y:
                inside = not inside
        j = i
    return inside


def box_polygon_overlap_fraction(
    box: Box,
    polygon: Polygon,
    *,
    samples_per_axis: int = 8,
) -> float:
    """Approximate fraction of a box covered by a polygon using grid sampling."""
    if len(polygon) < 3:
        return 0.0
    x, y, width, height = box
    if width <= 0 or height <= 0:
        return 0.0

    samples = max(1, samples_per_axis)
    hits = 0
    total = samples * samples
    for row in range(samples):
        py = y + (row + 0.5) * height / samples
        for col in range(samples):
            px = x + (col + 0.5) * width / samples
            if point_in_polygon((px, py), polygon):
                hits += 1
    return hits / total


def zone_membership(
    box: Box,
    zones: CalibrationZones,
    *,
    samples_per_axis: int = 8,
) -> ZoneMembership:
    center = box_center(box)
    return ZoneMembership(
        source_overlap=_max_overlap(box, zones.source_polygons, samples_per_axis),
        output_overlap=_max_overlap(box, zones.output_polygons, samples_per_axis),
        ignore_overlap=_max_overlap(box, zones.ignore_polygons, samples_per_axis),
        center_in_source=any(point_in_polygon(center, polygon) for polygon in zones.source_polygons),
        center_in_output=any(point_in_polygon(center, polygon) for polygon in zones.output_polygons),
        center_in_ignore=any(point_in_polygon(center, polygon) for polygon in zones.ignore_polygons),
    )


def gate_side(point: Point, gate: Gate) -> int:
    ax, ay = gate.start
    bx, by = gate.end
    px, py = point
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if cross > 0:
        return 1
    if cross < 0:
        return -1
    return 0


def gate_crossed_allowed_direction(previous: Point, current: Point, gate: Gate) -> bool:
    previous_side = gate_side(previous, gate)
    current_side = gate_side(current, gate)
    if previous_side == 0 or current_side == 0:
        return False
    return previous_side == gate.source_side and current_side == -gate.source_side


def _max_overlap(box: Box, polygons: list[Polygon], samples_per_axis: int) -> float:
    if not polygons:
        return 0.0
    return max(
        box_polygon_overlap_fraction(
            box,
            polygon,
            samples_per_axis=samples_per_axis,
        )
        for polygon in polygons
    )


def _point_on_segment(point: Point, start: Point, end: Point, *, epsilon: float = 1e-9) -> bool:
    px, py = point
    ax, ay = start
    bx, by = end
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > epsilon:
        return False
    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    if dot < -epsilon:
        return False
    squared_len = (bx - ax) ** 2 + (by - ay) ** 2
    return dot <= squared_len + epsilon
