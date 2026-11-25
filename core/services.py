"""Servicos de aplicacao: cada um tem uma responsabilidade (SRP) e recebe dependencias (DIP)."""
import random
import math

from . import events as ev
from .domain import City, Lot, LotKind, LotPlacement, Node, Road, RoadKind, UPGRADE_LADDER
from .errors import GameError
from .placement import LotPlacementService
from .road_state import AcidenteState, ObrasState
from . import config as cfg


class ZoningService:
    def __init__(self, city, treasury, bus, roads=None, land_validator=None):
        self.city, self.treasury, self.bus, self.roads = city, treasury, bus, roads
        self.placement = LotPlacementService(city, land_validator)

    def previsualizar(self, x, y, kind, map_width, map_height, rotation=0.0):
        return self.placement.preview(x, y, kind, map_width, map_height, rotation)

    def colocar(self, placement: LotPlacement, map_width: float, map_height: float) -> Lot:
        if not placement.valid:
            raise GameError(placement.reason or "Posicao invalida para o lote.")
        placement = self.placement.validar(placement, map_width, map_height)
        if not placement.valid or placement.road_id is None:
            raise GameError(placement.reason or "Posicao invalida para o lote.")
        if self.roads is None:
            raise GameError("O servico de vias nao esta disponivel.")
        if self.treasury.saldo < placement.kind.custo:
            raise GameError(
                f"Verba insuficiente: custa {placement.kind.custo:.0f}, "
                f"saldo {self.treasury.saldo:.0f}."
            )
        if placement.road_id not in self.city.roads:
            raise GameError("A via selecionada nao existe mais.")
        self.treasury.gastar(placement.kind.custo, f"construir {placement.kind.rotulo}")
        node = self.roads.criar_cruzamento_na_via(
            placement.road_id, placement.access_x, placement.access_y
        )
        lot = Lot(
            self.city.proximo_lote_id(), placement.kind, placement.x, placement.y,
            placement.width, placement.height, placement.angle, placement.road_id, node.id,
        )
        self.city.add_lot(lot)
        self.bus.publish(ev.CITY_CHANGED)
        return lot

    def construir(self, node_id: int, kind: LotKind):
        n = self.city.nodes.get(node_id)
        if not n:
            raise GameError("Cruzamento inexistente.")
        if n.lotes(kind) >= cfg.MAX_LOTES_POR_NO:
            raise GameError("Limite de lotes neste cruzamento.")
        self.treasury.gastar(kind.custo, f"construir {kind.rotulo}")
        n.adicionar_lote(kind)
        self.bus.publish(ev.CITY_CHANGED)

    def demolir(self, node_id: int, kind: LotKind):
        n = self.city.nodes.get(node_id)
        if not n or n.lotes(kind) <= 0:
            raise GameError(f"Nao ha lote {kind.rotulo} neste local.")
        setattr(n, kind.campo, n.lotes(kind) - 1)
        self.bus.publish(ev.CITY_CHANGED)

    def demolir_lote(self, lot_id: int):
        if lot_id not in self.city.lots:
            raise GameError("Construcao inexistente.")
        del self.city.lots[lot_id]
        self.bus.publish(ev.CITY_CHANGED)


class RoadService:
    def __init__(self, city, treasury, bus, road_factory):
        self.city, self.treasury, self.bus, self.factory = city, treasury, bus, road_factory

    def _valida(self, kind: RoadKind, faixas: int):
        lo, hi = kind.faixas
        if not lo <= faixas <= hi:
            raise GameError(f"{kind.rotulo} aceita de {lo} a {hi} faixas por sentido.")

    def _road(self, rid) -> Road:
        if rid not in self.city.roads:
            raise GameError("Via inexistente.")
        return self.city.roads[rid]

    def criar_cruzamento(self, x, y):
        from .domain import Node
        n = Node(self.city.proximo_no_id(), "Cruzamento", x, y)
        self.city.add_node(n)
        self.bus.publish(ev.CITY_CHANGED)
        return n

    def construir(self, u, v, kind, faixas, mao_unica) -> Road:
        if u == v or u not in self.city.nodes or v not in self.city.nodes:
            raise GameError("Escolha dois cruzamentos diferentes.")
        if self.city.via_entre(u, v):
            raise GameError("Ja existe via entre estes cruzamentos; melhore-a.")
        self._valida(kind, faixas)
        a, b = self.city.nodes[u], self.city.nodes[v]
        novos_cruzamentos = []
        pontos_via = {}
        cortes = {}
        for existente in list(self.city.roads.values()):
            c, d = self.city.nodes[existente.u], self.city.nodes[existente.v]
            intersecao = self._intersecao((a.x, a.y), (b.x, b.y), (c.x, c.y), (d.x, d.y))
            if intersecao is None:
                continue
            t, s = intersecao
            if not (1e-8 < t < 1 - 1e-8 or 1e-8 < s < 1 - 1e-8):
                continue
            x, y = a.x + t * (b.x - a.x), a.y + t * (b.y - a.y)
            if s <= 1e-8:
                node_id = existente.u
            elif s >= 1 - 1e-8:
                node_id = existente.v
            else:
                node_id = pontos_via.get(round(t, 9))
                if node_id is None:
                    node = Node(self.city.proximo_no_id(), "Cruzamento", x, y)
                    novos_cruzamentos.append(node)
                    node_id = node.id
            if 1e-8 < s < 1 - 1e-8:
                cortes.setdefault(existente.id, []).append((s, node_id))
            if 1e-8 < t < 1 - 1e-8:
                pontos_via[round(t, 9)] = node_id

        segmentos = [0.0] + sorted(t for t in pontos_via) + [1.0]
        comprimento = max(0.5, math.hypot(b.x - a.x, b.y - a.y) * cfg.UNIDADES_POR_MAPA)
        custo_unitario = kind.custo_faixa * faixas * (1 if mao_unica else 2)
        custo = sum(custo_unitario * max(0.5, comprimento * (fim - inicio))
                    for inicio, fim in zip(segmentos, segmentos[1:]))
        self.treasury.gastar(custo, "construir via")

        novos_nos = {n.id: n for n in novos_cruzamentos}
        self.city.nodes.update(novos_nos)
        for road_id, pontos in cortes.items():
            self._dividir_via(self.city.roads[road_id], pontos)

        pontos_via = [(0.0, u)] + sorted(
            (t, node_id) for t, node_id in pontos_via.items()
        ) + [(1.0, v)]
        r = None
        for (inicio, origem), (fim, destino) in zip(pontos_via, pontos_via[1:]):
            trecho = self.factory.criar(self.city, origem, destino, kind, faixas, mao_unica)
            trecho.comprimento = round(max(0.5, comprimento * (fim - inicio)), 2)
            self.city.add_road(trecho)
            r = r or trecho
        self.bus.publish(ev.CITY_CHANGED)
        return r

    def construir_por_coordenadas(self, x1, y1, x2, y2, kind, faixas, mao_unica):
        criados = []

        def resolver(x, y):
            mais_proximo = min(
                self.city.nodes.values(),
                key=lambda n: math.hypot(n.x - x, n.y - y),
                default=None,
            )
            if mais_proximo and math.hypot(mais_proximo.x - x, mais_proximo.y - y) <= 0.003:
                return mais_proximo.id
            node = Node(self.city.proximo_no_id(), "Cruzamento", x, y)
            self.city.add_node(node)
            criados.append(node.id)
            return node.id

        u, v = resolver(x1, y1), resolver(x2, y2)
        if u == v:
            for node_id in criados:
                self.city.nodes.pop(node_id, None)
            raise GameError("Escolha dois pontos diferentes.")
        try:
            return self.construir(u, v, kind, faixas, mao_unica)
        except GameError:
            for node_id in criados:
                self.city.nodes.pop(node_id, None)
            raise

    @staticmethod
    def _intersecao(a, b, c, d):
        ab = (b[0] - a[0], b[1] - a[1])
        cd = (d[0] - c[0], d[1] - c[1])
        produto = ab[0] * cd[1] - ab[1] * cd[0]
        if abs(produto) < 1e-12:
            return None
        ac = (c[0] - a[0], c[1] - a[1])
        t = (ac[0] * cd[1] - ac[1] * cd[0]) / produto
        s = (ac[0] * ab[1] - ac[1] * ab[0]) / produto
        if -1e-8 <= t <= 1 + 1e-8 and -1e-8 <= s <= 1 + 1e-8:
            return max(0.0, min(1.0, t)), max(0.0, min(1.0, s))
        return None

    def _dividir_via(self, road, pontos):
        comprimento_original = road.comprimento
        ordenados = [(0.0, road.u)] + sorted(pontos) + [(1.0, road.v)]
        primeiro, segundo = ordenados[0], ordenados[1]
        road.v = segundo[1]
        road.comprimento = round(max(0.5, comprimento_original * (segundo[0] - primeiro[0])), 2)
        for (inicio, origem), (fim, destino) in zip(ordenados[1:], ordenados[2:]):
            trecho = Road(
                self.city.proxima_via_id(), origem, destino, road.kind, road.faixas,
                road.mao_unica, round(max(0.5, comprimento_original * (fim - inicio)), 2), road.state,
            )
            self.city.add_road(trecho)

    def criar_cruzamento_na_via(self, road_id, x, y):
        road = self._road(road_id)
        a, b = self.city.nodes[road.u], self.city.nodes[road.v]
        dx, dy = b.x - a.x, b.y - a.y
        t = 0 if dx == dy == 0 else max(0.0, min(1.0, ((x - a.x) * dx + (y - a.y) * dy) / (dx * dx + dy * dy)))
        if t <= 1e-5:
            return a
        if t >= 1 - 1e-5:
            return b
        node = Node(self.city.proximo_no_id(), "Lote", a.x + t * dx, a.y + t * dy)
        self.city.add_node(node)
        self._dividir_via(road, [(t, node.id)])
        self.bus.publish(ev.CITY_CHANGED)
        return node

    def demolir(self, road_id):
        road = self._road(road_id)
        endpoints = {road.u, road.v}
        for lot in self.city.lots.values():
            if lot.access_node_id not in endpoints:
                continue
            remaining = [
                candidate for candidate in self.city.roads.values()
                if candidate.id != road_id
                and lot.access_node_id in (candidate.u, candidate.v)
            ]
            if not remaining:
                raise GameError("Demolir ou realocar os lotes ligados a esta via primeiro.")
            if lot.road_id == road_id:
                lot.road_id = remaining[0].id
        del self.city.roads[road_id]
        self.bus.publish(ev.CITY_CHANGED)
        return road_id

    def melhorar(self, rid) -> Road:
        r = self._road(rid)
        prox = r.proxima_melhoria()
        if not prox:
            raise GameError("A via ja esta no nivel maximo.")
        kind, faixas = prox
        custo = max(300, r.custo(kind, faixas) - 0.5 * r.custo())
        self.treasury.gastar(custo, "melhorar via")
        r.kind, r.faixas = kind, faixas
        self.bus.publish(ev.CITY_CHANGED)
        return r

    def inverter(self, rid) -> Road:
        r = self._road(rid)
        if not r.mao_unica:
            raise GameError("So vias de mao unica podem ser invertidas.")
        r.inverter()
        self.bus.publish(ev.CITY_CHANGED)
        return r

    def alternar_mao(self, rid) -> Road:
        r = self._road(rid)
        if r.mao_unica:
            self.treasury.gastar(r.custo(mao_unica=False) * 0.5, "duplicar mao")
        r.mao_unica = not r.mao_unica
        self.bus.publish(ev.CITY_CHANGED)
        return r


class EconomyService:
    def __init__(self, city, treasury):
        self.city, self.treasury = city, treasury

    def arrecadar(self, atendimento: float) -> float:
        """Quanto mais gente e melhor o atendimento viario, mais imposto."""
        imposto = round(self.city.populacao * cfg.IMPOSTO_POR_HAB * min(1.0, atendimento), 2)
        self.treasury.receber(imposto, "impostos")
        return imposto


class RandomEventService:
    def __init__(self, city, bus, rng=None, prob=cfg.PROB_EVENTO_POR_CICLO):
        self.city, self.bus, self.rng, self.prob = city, bus, rng or random.Random(), prob

    def avancar(self):
        for r in self.city.roads.values():
            antes = r.state
            r.state = antes.tick()
            if antes.ativo and not r.state.ativo:
                self.bus.publish(ev.ROAD_EVENT_ENDED, road_id=r.id)
        livres = [r for r in self.city.roads.values() if not r.state.ativo]
        if livres and self.rng.random() < self.prob:
            r = self.rng.choice(livres)
            dur = self.rng.randint(2, 4)
            r.state = self.rng.choice([ObrasState, AcidenteState])(dur)
            self.bus.publish(ev.ROAD_EVENT_STARTED, road_id=r.id, tipo=r.state.nome, duracao=dur)
        self.bus.publish(ev.CITY_CHANGED)
