"""Converte coordenadas normalizadas do dominio (0..1, y para baixo) em coordenadas do mundo Arcade."""
import math

from core.placement import lot_polygon

class MapProjection:
    def __init__(self, largura: float, altura: float):
        self.w, self.h = largura, altura

    def to_world(self, nx, ny): return nx * self.w, (1 - ny) * self.h
    def to_norm(self, wx, wy): return wx / self.w, 1 - wy / self.h


def dist_ponto_segmento(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class Picker:
    """Information Expert da geometria: acha o no/via sob o mouse."""

    def __init__(self, city, proj: MapProjection):
        self.city, self.proj = city, proj

    def no(self, wx, wy, raio):
        melhor = None
        for n in self.city.nodes.values():
            d = math.hypot(wx - self.proj.to_world(n.x, n.y)[0], wy - self.proj.to_world(n.x, n.y)[1])
            if d <= raio and (melhor is None or d < melhor[0]):
                melhor = (d, n.id)
        return melhor[1] if melhor else None

    def via(self, wx, wy, tol):
        candidato = self.ponto_via(wx, wy)
        return candidato[0] if candidato and candidato[1] <= tol else None

    def ponto_via(self, wx, wy):
        melhor = None
        for r in self.city.roads.values():
            ax, ay = self.proj.to_world(self.city.nodes[r.u].x, self.city.nodes[r.u].y)
            bx, by = self.proj.to_world(self.city.nodes[r.v].x, self.city.nodes[r.v].y)
            d = dist_ponto_segmento(wx, wy, ax, ay, bx, by)
            if melhor is None or d < melhor[0]:
                t = 0 if ax == bx and ay == by else max(
                    0, min(1, ((wx - ax) * (bx - ax) + (wy - ay) * (by - ay)) /
                           ((bx - ax) ** 2 + (by - ay) ** 2))
                )
                melhor = (d, r.id, ax + t * (bx - ax), ay + t * (by - ay))
        if not melhor:
            return None
        _, road_id, px, py = melhor
        nx, ny = self.proj.to_norm(px, py)
        return road_id, melhor[0], nx, ny

    def lote(self, wx, wy, map_width, map_height):
        for lot in self.city.lots.values():
            polygon = lot_polygon(lot, map_width, map_height)
            dentro = False
            anterior = polygon[-1]
            for atual in polygon:
                if (atual[1] > wy) != (anterior[1] > wy):
                    cruzamento_x = (anterior[0] - atual[0]) * (wy - atual[1]) / (
                        anterior[1] - atual[1]
                    ) + atual[0]
                    if wx < cruzamento_x:
                        dentro = not dentro
                anterior = atual
            if dentro:
                return lot.id
        return None
