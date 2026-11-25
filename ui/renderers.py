"""Renderizacao (somente leitura do dominio). Cada renderer tem uma responsabilidade."""
import math
import os
import random

import arcade

from core.domain import Lot
from core.placement import lot_polygon, road_width

COR_STATUS = {"verde": (46, 204, 64, 235), "amarelo": (255, 214, 10, 235),
              "vermelho": (231, 40, 40, 240), "cinza": (110, 110, 110, 235)}
ASFALTO = (176, 178, 186)          # estilo do mapa de Key Lento: via cinza-clara com miolo claro
MIOLO = (232, 230, 205)
BORDA = (92, 96, 108)
COR_LOTE = {
    "casas": (0, 235, 55, 245),
    "comercios": (30, 104, 255, 245),
    "industrias": (255, 224, 0, 245),
}
COR_LOTE_KIND = {
    "casa": COR_LOTE["casas"],
    "comercio": COR_LOTE["comercios"],
    "industria": COR_LOTE["industrias"],
}


class BaseMapRenderer:
    def __init__(self, caminho):
        self.tex = arcade.load_texture(caminho) if os.path.exists(caminho) else None
        self.w, self.h = (self.tex.width, self.tex.height) if self.tex else (1650, 2260)

    def draw(self):
        if self.tex:
            arcade.draw_texture_rect(self.tex, arcade.XYWH(self.w / 2, self.h / 2, self.w, self.h))
        else:
            arcade.draw_lbwh_rectangle_filled(0, 0, self.w, self.h, (30, 140, 170))


class RoadRenderer:
    """Largura em unidades de mundo; cor interna reflete o fluxo (verde/amarelo/vermelho)."""

    def __init__(self, city, proj, escala=1.0):
        self.city, self.proj, self.escala = city, proj, escala

    def _pts(self, r):
        a, b = self.city.nodes[r.u], self.city.nodes[r.v]
        return (*self.proj.to_world(a.x, a.y), *self.proj.to_world(b.x, b.y))

    def draw(self, report, selecionada=None):
        cores = {}
        if report:
            for e in report.arestas:
                cur = cores.get(e.key[0])
                if cur is None or e.utilizacao > cur[1]:
                    cores[e.key[0]] = (e.cor, e.utilizacao)
        for r in self.city.roads.values():
            x1, y1, x2, y2 = self._pts(r)
            larg = road_width(r, self.proj.w)
            arcade.draw_line(x1, y1, x2, y2, BORDA, larg + 1.4 * self.escala)
            arcade.draw_line(x1, y1, x2, y2, ASFALTO, larg)
            cor = COR_STATUS.get(cores.get(r.id, ("cinza", 0))[0] if report else "cinza")
            if r.state.ativo:
                cor = COR_STATUS["cinza"] if r.state.nome == "obra" else (255, 140, 0, 240)
            elif not report:
                cor = (*MIOLO, 255)
            arcade.draw_line(x1, y1, x2, y2, cor, max(0.6, larg * 0.45))
            if r.id == selecionada:
                arcade.draw_line(x1, y1, x2, y2, (255, 255, 255, 200), larg + 2.5 * self.escala)
            if r.mao_unica:
                self._seta(x1, y1, x2, y2, larg)

    def _seta(self, x1, y1, x2, y2, larg):
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ang = math.atan2(y2 - y1, x2 - x1)
        t = larg * 0.9
        pts = [(mx + math.cos(ang) * t, my + math.sin(ang) * t),
               (mx + math.cos(ang + 2.5) * t, my + math.sin(ang + 2.5) * t),
               (mx + math.cos(ang - 2.5) * t, my + math.sin(ang - 2.5) * t)]
        arcade.draw_triangle_filled(*pts[0], *pts[1], *pts[2], (20, 20, 30, 230))


class LotRenderer:
    def __init__(self, city, proj, escala=1.0):
        self.city, self.proj, self.escala = city, proj, escala

    def draw(self, preview=None, selecionado=None):
        for lot in self.city.lots.values():
            polygon = lot_polygon(lot, self.proj.w, self.proj.h)
            arcade.draw_polygon_filled(polygon, COR_LOTE_KIND[lot.kind.rotulo])
            arcade.draw_polygon_outline(polygon, (24, 35, 44, 230), 1.2 * self.escala)
            if lot.id == selecionado:
                arcade.draw_polygon_outline(polygon, (255, 255, 255, 255), 2.0 * self.escala)

        if preview:
            candidate = Lot(
                -1, preview.kind, preview.x, preview.y, preview.width,
                preview.height, preview.angle, preview.road_id or -1,
            )
            color = (22, 210, 78, 115) if preview.valid else (235, 54, 60, 125)
            polygon = lot_polygon(candidate, self.proj.w, self.proj.h)
            arcade.draw_polygon_filled(polygon, color)
            arcade.draw_polygon_outline(polygon, color[:3] + (255,), 2.0 * self.escala)

        for n in self.city.nodes.values():
            x, y = self.proj.to_world(n.x, n.y)
            arcade.draw_circle_filled(x, y, 1.1 * self.escala, (224, 228, 232, 255))
            arcade.draw_circle_outline(
                x, y, 1.8 * self.escala,
                (53, 61, 70, 235), 0.8 * self.escala,
            )


class CarSwarm:
    """Carros animados: quantidade proporcional ao fluxo; velocidade cai quando a via satura."""

    def __init__(self, city, proj, escala=1.0, seed=7):
        self.city, self.proj, self.escala, self.rng = city, proj, escala, random.Random(seed)
        self.carros = []

    def reconstruir(self, report):
        self.carros = []
        if not report:
            return
        for e in report.arestas:
            if e.flow <= 0:
                continue
            n = max(1, min(10, round(e.flow / 150)))
            for k in range(n):
                self.carros.append([e, self.rng.random(), self.rng.choice(
                    [(250, 250, 250), (60, 60, 70), (200, 60, 60), (70, 120, 220), (240, 190, 40)])])

    def update(self, dt):
        for c in self.carros:
            v = 0.5 * (1 - 0.75 * c[0].utilizacao)
            c[1] = (c[1] + v * dt / max(0.3, self._len(c[0]))) % 1.0

    def _len(self, e):
        a, b = self.city.nodes[e.u], self.city.nodes[e.v]
        return max(0.05, math.hypot(*(p - q for p, q in zip(self.proj.to_world(a.x, a.y), self.proj.to_world(b.x, b.y)))) / 30)

    def draw(self):
        s = self.escala
        for e, t, cor in self.carros:
            a, b = self.city.nodes[e.u], self.city.nodes[e.v]
            ax, ay = self.proj.to_world(a.x, a.y)
            bx, by = self.proj.to_world(b.x, b.y)
            ang = math.atan2(by - ay, bx - ax)
            ox, oy = math.sin(ang) * 0.9 * s, -math.cos(ang) * 0.9 * s   # lado direito da via
            arcade.draw_circle_filled(ax + (bx - ax) * t + ox, ay + (by - ay) * t + oy, 0.75 * s, cor)
