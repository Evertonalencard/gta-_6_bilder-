"""Creator: quem cria as entidades e quem tem os dados para inicializa-las."""
import json
import math

from . import config as cfg
from .domain import City, Lot, LotKind, Node, Road, RoadKind
from .placement import LotPlacementService


class RoadFactory:
    def criar(self, city: City, u: int, v: int, kind: RoadKind, faixas: int, mao_unica: bool) -> Road:
        a, b = city.nodes[u], city.nodes[v]
        comp = max(0.5, math.hypot(a.x - b.x, a.y - b.y) * cfg.UNIDADES_POR_MAPA)
        return Road(city.proxima_via_id(), u, v, kind, faixas, mao_unica, round(comp, 2))


class CityFactory:
    """Cidade inicial: escada de 20 cruzamentos ao longo de Key Lento (coordenadas normalizadas
    do mapa Leonida; ajuste A/B depois de calibrar com o editor de cruzamentos)."""

    A = (0.619, 0.785)       # extremo norte (perto da ponte 1A)
    B = (0.516, 0.864)       # extremo sul

    def __init__(self, roads: RoadFactory):
        self.roads = roads

    def key_lento(self) -> City:
        c, n = City(), 10
        dx, dy = self.B[0] - self.A[0], self.B[1] - self.A[1]
        norma = math.hypot(dx, dy)
        px, py = -dy / norma * 0.006, dx / norma * 0.006
        for i in range(n):
            t = i / (n - 1)
            cx, cy = self.A[0] + dx * t, self.A[1] + dy * t
            c.add_node(Node(2 * i, f"KL-{i}a", cx + px, cy + py))
            c.add_node(Node(2 * i + 1, f"KL-{i}b", cx - px, cy - py))
        c.nodes[0].estadio, c.nodes[0].nome = True, "Estadio"
        c.nodes[2 * n - 1].saida, c.nodes[2 * n - 1].nome = True, "Saida"
        for i in range(2, 8, 1): c.nodes[i].casas = 3
        for i in range(8, 14): c.nodes[i].comercios = 4
        for i in range(14, 18): c.nodes[i].industrias = 3
        for i in range(n):
            c.add_road(self.roads.criar(c, 2 * i, 2 * i + 1, RoadKind.RUA, 1, False))
            if i + 1 < n:
                c.add_road(self.roads.criar(c, 2 * i, 2 * i + 2, RoadKind.AVENIDA, 2, False))
                c.add_road(self.roads.criar(c, 2 * i + 1, 2 * i + 3, RoadKind.RUA, 1, i % 4 == 3))
        return c


def materializar_zoneamento_legado(city, map_width, map_height, land_validator=None):
    """Converte os contadores antigos por cruzamento em construcoes individuais."""
    if city.lots or not city.roads:
        return
    placement_service = LotPlacementService(city, land_validator)
    materialized_any = False
    for node in city.nodes.values():
        for kind in (LotKind.CASA, LotKind.COMERCIO, LotKind.INDUSTRIA):
            quantidade = node.lotes(kind)
            for _ in range(quantidade):
                placement = None
                for road in list(city.roads.values()):
                    if node.id not in (road.u, road.v):
                        continue
                    a, b = city.nodes[road.u], city.nodes[road.v]
                    start = (a.x * map_width, (1 - a.y) * map_height)
                    end = (b.x * map_width, (1 - b.y) * map_height)
                    dx, dy = end[0] - start[0], end[1] - start[1]
                    length = math.hypot(dx, dy)
                    if length == 0:
                        continue
                    normal = (-dy / length, dx / length)
                    for t in (0.25, 0.5, 0.75):
                        for side in (-1, 1):
                            x = start[0] + t * dx + normal[0] * side
                            y = start[1] + t * dy + normal[1] * side
                            candidate = placement_service.preview(
                                x, y, kind, map_width, map_height
                            )
                            if candidate.valid:
                                placement = candidate
                                break
                        if placement:
                            break
                    if placement:
                        break
                if not placement or placement.road_id is None:
                    continue
                road = city.roads[placement.road_id]
                access_x = placement.access_x * map_width
                access_y = (1 - placement.access_y) * map_height
                access_node = min(
                    (city.nodes[road.u], city.nodes[road.v]),
                    key=lambda endpoint: math.hypot(
                        endpoint.x * map_width - access_x,
                        (1 - endpoint.y) * map_height - access_y,
                    ),
                )
                city.add_lot(Lot(
                    city.proximo_lote_id(), kind, placement.x, placement.y,
                    placement.width, placement.height, placement.angle,
                    placement.road_id, access_node.id,
                ))
                materialized_any = True
    if materialized_any:
        for node in city.nodes.values():
            node.casas = node.comercios = node.industrias = 0


class CityRepository:
    """Persistencia JSON: monte o grafo no mapa uma vez e reutilize."""

    def __init__(self, caminho: str):
        self.caminho = caminho

    def salvar(self, city: City):
        data = {"nodes": [n.__dict__ for n in city.nodes.values()],
                "roads": [{"id": r.id, "u": r.u, "v": r.v, "kind": r.kind.name, "faixas": r.faixas,
                           "mao_unica": r.mao_unica, "comprimento": r.comprimento} for r in city.roads.values()],
                "lots": [{"id": l.id, "kind": l.kind.name, "x": l.x, "y": l.y,
                          "width": l.width, "height": l.height, "angle": l.angle,
                          "road_id": l.road_id, "access_node_id": l.access_node_id}
                         for l in city.lots.values()]}
        with open(self.caminho, "w") as f:
            json.dump(data, f, indent=1)

    def carregar(self) -> City:
        with open(self.caminho) as f:
            data = json.load(f)
        c = City()
        for n in data["nodes"]: c.add_node(Node(**n))
        for r in data["roads"]:
            c.add_road(Road(r["id"], r["u"], r["v"], RoadKind[r["kind"]], r["faixas"], r["mao_unica"], r["comprimento"]))
        for lot in data.get("lots", []):
            c.add_lot(Lot(
                lot["id"], LotKind[lot["kind"]], lot["x"], lot["y"],
                lot["width"], lot["height"], lot["angle"], lot["road_id"],
                lot.get("access_node_id"),
            ))
        return c
