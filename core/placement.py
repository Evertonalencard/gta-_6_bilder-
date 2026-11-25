"""Geometria de encaixe e validacao dos lotes, independente do renderizador."""
import math
from typing import Callable, Optional, Sequence, Tuple

from . import config as cfg
from .domain import City, Lot, LotPlacement, Road, RoadKind

Point = Tuple[float, float]
LandValidator = Callable[[float, float], bool]


def road_width(road: Road, map_width: float) -> float:
    scale = map_width / 1650
    base = 2.4 if road.kind is RoadKind.RUA else 4.2
    faixa_extra = road.faixas - min(road.kind.faixas)
    return (base + faixa_extra * 0.7) * scale


def lot_polygon(lot: Lot, map_width: float, map_height: float) -> Tuple[Point, ...]:
    return _rectangle(lot.x * map_width, (1 - lot.y) * map_height,
                      lot.width, lot.height, lot.angle)


def _rectangle(cx: float, cy: float, width: float, height: float, angle: float) -> Tuple[Point, ...]:
    cosine, sine = math.cos(angle), math.sin(angle)
    points = []
    for local_x, local_y in (
        (-width / 2, -height / 2), (width / 2, -height / 2),
        (width / 2, height / 2), (-width / 2, height / 2),
    ):
        points.append((cx + local_x * cosine - local_y * sine,
                       cy + local_x * sine + local_y * cosine))
    return tuple(points)


def _road_polygon(road: Road, city: City, map_width: float, map_height: float) -> Tuple[Point, ...]:
    a, b = city.nodes[road.u], city.nodes[road.v]
    ax, ay = a.x * map_width, (1 - a.y) * map_height
    bx, by = b.x * map_width, (1 - b.y) * map_height
    dx, dy = bx - ax, by - ay
    length = max(1e-9, math.hypot(dx, dy))
    nx, ny = -dy / length * road_width(road, map_width) / 2, dx / length * road_width(road, map_width) / 2
    return ((ax + nx, ay + ny), (bx + nx, by + ny),
            (bx - nx, by - ny), (ax - nx, ay - ny))


def _polygons_overlap(first: Sequence[Point], second: Sequence[Point]) -> bool:
    for polygon in (first, second):
        for index, point in enumerate(polygon):
            following = polygon[(index + 1) % len(polygon)]
            axis = (-(following[1] - point[1]), following[0] - point[0])
            first_projection = [x * axis[0] + y * axis[1] for x, y in first]
            second_projection = [x * axis[0] + y * axis[1] for x, y in second]
            if max(first_projection) <= min(second_projection) or max(second_projection) <= min(first_projection):
                return False
    return True


def _point_segment_distance(point: Point, start: Point, end: Point) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    denominator = dx * dx + dy * dy
    t = 0 if denominator == 0 else max(
        0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / denominator)
    )
    return math.hypot(point[0] - (start[0] + t * dx), point[1] - (start[1] + t * dy))


class LotPlacementService:
    def __init__(self, city: City, land_validator: Optional[LandValidator] = None):
        self.city = city
        self.land_validator = land_validator

    def preview(self, x: float, y: float, kind, map_width: float, map_height: float,
                rotation_offset: float = 0.0) -> LotPlacement:
        nearest = None
        for road in self.city.roads.values():
            a, b = self.city.nodes[road.u], self.city.nodes[road.v]
            start = (a.x * map_width, (1 - a.y) * map_height)
            end = (b.x * map_width, (1 - b.y) * map_height)
            dx, dy = end[0] - start[0], end[1] - start[1]
            denominator = dx * dx + dy * dy
            t = 0 if denominator == 0 else max(
                0.0, min(1.0, ((x - start[0]) * dx + (y - start[1]) * dy) / denominator)
            )
            point = (start[0] + t * dx, start[1] + t * dy)
            distance = math.hypot(x - point[0], y - point[1])
            if nearest is None or distance < nearest[0]:
                nearest = (distance, road, start, end, point, t)

        width, height = cfg.LOTE_LARGURA * map_width / 1650, cfg.LOTE_PROFUNDIDADE * map_width / 1650
        if nearest is None:
            return LotPlacement(kind, x / map_width, 1 - y / map_height, width, height,
                                rotation_offset, None, None, None, False, "Construa uma via primeiro.")

        distance, road, start, end, access, _ = nearest
        dx, dy = end[0] - start[0], end[1] - start[1]
        angle = math.atan2(dy, dx)
        normal = (-math.sin(angle), math.cos(angle))
        side_value = (x - access[0]) * normal[0] + (y - access[1]) * normal[1]
        side = 1.0 if side_value >= 0 else -1.0
        width_road = road_width(road, map_width)
        offset = width_road / 2 + height / 2 + cfg.DISTANCIA_LOTE_VIA * map_width / 1650
        center = (access[0] + normal[0] * side * offset,
                  access[1] + normal[1] * side * offset)
        placement = LotPlacement(
            kind, center[0] / map_width, 1 - center[1] / map_height, width, height,
            angle + rotation_offset, road.id, access[0] / map_width, 1 - access[1] / map_height,
            True,
        )
        return self.validar(placement, map_width, map_height, distance)

    def validar(self, placement: LotPlacement, map_width: float, map_height: float,
                cursor_distance: Optional[float] = None) -> LotPlacement:
        if placement.road_id not in self.city.roads:
            return self._invalid(placement, "O lote precisa ter acesso a uma via.")
        road = self.city.roads[placement.road_id]
        polygon = _rectangle(
            placement.x * map_width, (1 - placement.y) * map_height,
            placement.width, placement.height, placement.angle,
        )
        if any(x < 0 or x > map_width or y < 0 or y > map_height for x, y in polygon):
            return self._invalid(placement, "O lote ultrapassa os limites do mapa.")
        if cursor_distance is not None and cursor_distance > 18 * map_width / 1650:
            return self._invalid(placement, "Posicione o lote perto de uma via.")

        a, b = self.city.nodes[road.u], self.city.nodes[road.v]
        road_start = (a.x * map_width, (1 - a.y) * map_height)
        road_end = (b.x * map_width, (1 - b.y) * map_height)
        road_dx, road_dy = road_end[0] - road_start[0], road_end[1] - road_start[1]
        road_length = math.hypot(road_dx, road_dy)
        road_angle = math.atan2(road_dy, road_dx)
        if abs(math.sin(placement.angle - road_angle)) > cfg.TOLERANCIA_ORIENTACAO_LOTE:
            return self._invalid(placement, "Gire o lote para alinhar sua face com a via.")
        if placement.access_x is None or placement.access_y is None:
            return self._invalid(placement, "O lote precisa ter acesso a uma via.")
        access = (placement.access_x * map_width, (1 - placement.access_y) * map_height)
        center = (placement.x * map_width, (1 - placement.y) * map_height)
        if _point_segment_distance(access, road_start, road_end) > 2 * map_width / 1650:
            return self._invalid(placement, "O ponto de acesso precisa estar sobre a via.")
        normal = (-road_dy / max(road_length, 1e-9), road_dx / max(road_length, 1e-9))
        frontage_distance = abs((center[0] - access[0]) * normal[0]
                                + (center[1] - access[1]) * normal[1])
        expected_distance = (
            (road_width(road, map_width) + placement.height) / 2
            + cfg.DISTANCIA_LOTE_VIA * map_width / 1650
        )
        if abs(frontage_distance - expected_distance) > 3 * map_width / 1650:
            return self._invalid(placement, "Uma face do lote deve ficar junto a via.")
        tangent = (road_dx / max(road_length, 1e-9), road_dy / max(road_length, 1e-9))
        access_along = ((access[0] - road_start[0]) * tangent[0]
                        + (access[1] - road_start[1]) * tangent[1])
        overlap = max(
            0.0,
            min(road_length, access_along + placement.width / 2)
            - max(0.0, access_along - placement.width / 2),
        )
        if overlap < placement.width * 0.65:
            return self._invalid(placement, "O lote precisa de uma face suficiente junto a via.")

        if self.land_validator:
            steps_x = max(2, math.ceil(placement.width / 4))
            steps_y = max(2, math.ceil(placement.height / 4))
            cosine, sine = math.cos(placement.angle), math.sin(placement.angle)
            for ix in range(steps_x + 1):
                local_x = (ix / steps_x - 0.5) * placement.width
                for iy in range(steps_y + 1):
                    local_y = (iy / steps_y - 0.5) * placement.height
                    px = placement.x * map_width + local_x * cosine - local_y * sine
                    py = (1 - placement.y) * map_height + local_x * sine + local_y * cosine
                    if not self.land_validator(px / map_width, 1 - py / map_height):
                        return self._invalid(placement, "Nao e possivel construir sobre a agua.")

        for lot in self.city.lots.values():
            if _polygons_overlap(polygon, lot_polygon(lot, map_width, map_height)):
                return self._invalid(placement, "O lote sobrepoe outra construcao.")

        for other_road in self.city.roads.values():
            road_polygon = _road_polygon(other_road, self.city, map_width, map_height)
            if _polygons_overlap(polygon, road_polygon):
                return self._invalid(placement, "O lote sobrepoe uma estrada.")

        return placement

    @staticmethod
    def _invalid(placement: LotPlacement, reason: str) -> LotPlacement:
        return LotPlacement(
            placement.kind, placement.x, placement.y, placement.width, placement.height,
            placement.angle, placement.road_id, placement.access_x, placement.access_y,
            False, reason,
        )
