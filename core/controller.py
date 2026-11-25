"""GRASP Controller: unico ponto de entrada da UI para o dominio (fachada)."""
from dataclasses import dataclass
from typing import Optional

from . import events as ev
from .analysis import FlowReport, TrafficAnalyzer, WhatIfService
from .demand import CommuteDemand, DemandStrategy, StadiumEventDemand
from .domain import City, LotKind, LotPlacement, RoadKind
from .errors import InsufficientFunds


@dataclass
class RushResult:
    report: FlowReport
    status: str          # sucesso | congestionada | travou
    bonus: float


class GameController:
    def __init__(self, city: City, treasury, bus, zoning, roads, economy, random_events,
                 analyzer: TrafficAnalyzer, what_if: WhatIfService, ciclo=0):
        self.city, self.treasury, self.bus = city, treasury, bus
        self.zoning, self.roads, self.economy, self.random_events = zoning, roads, economy, random_events
        self.analyzer, self.what_if = analyzer, what_if
        self.ciclo = ciclo
        self.veiculos_evento = 3000

    # ---- consultas ----
    def analisar(self, evento: bool = False) -> FlowReport:
        return self.analyzer.analisar(self.city, self._demanda(evento))

    def _demanda(self, evento: bool):
        strat: DemandStrategy = StadiumEventDemand(self.veiculos_evento) if evento else CommuteDemand()
        return strat.build(self.city)

    # ---- construcao ----
    def criar_cruzamento(self, x, y): return self.roads.criar_cruzamento(x, y)
    def construir_lote(self, node_id, kind: LotKind): self.zoning.construir(node_id, kind)
    def construir_lote_na_via(self, road_id, x, y, kind: LotKind):
        if self.treasury.saldo < kind.custo:
            raise InsufficientFunds(f"Verba insuficiente: custa {kind.custo:.0f}, saldo {self.treasury.saldo:.0f}.")
        node = self.roads.criar_cruzamento_na_via(road_id, x, y)
        self.zoning.construir(node.id, kind)
        return node
    def previsualizar_lote(self, x, y, kind: LotKind, map_width, map_height, rotation=0.0):
        return self.zoning.previsualizar(x, y, kind, map_width, map_height, rotation)
    def construir_lote_posicionado(self, placement: LotPlacement, map_width, map_height):
        return self.zoning.colocar(placement, map_width, map_height)
    def construir_via(self, u, v, kind: RoadKind, faixas, mao_unica): return self.roads.construir(u, v, kind, faixas, mao_unica)
    def construir_via_por_coordenadas(self, x1, y1, x2, y2, kind, faixas, mao_unica):
        return self.roads.construir_por_coordenadas(x1, y1, x2, y2, kind, faixas, mao_unica)
    def demolir_via(self, road_id): return self.roads.demolir(road_id)
    def demolir_lote(self, node_id, kind: LotKind): return self.zoning.demolir(node_id, kind)
    def demolir_construcao(self, lot_id): return self.zoning.demolir_lote(lot_id)
    def melhorar_via(self, rid): return self.roads.melhorar(rid)
    def inverter_via(self, rid): return self.roads.inverter(rid)
    def alternar_mao(self, rid): return self.roads.alternar_mao(rid)

    # ---- cenarios "E se?" ----
    def cenario_a(self, rid, modo="interditar", evento=True):
        return self.what_if.cenario_a(self.city, self._demanda(evento), rid, modo)

    def cenario_b(self, x=600, evento=True):
        return self.what_if.cenario_b(self.city, self._demanda(evento), x)

    # ---- tempo ----
    def avancar_tempo(self, pico: bool = False) -> Optional[RushResult]:
        rep = self.analisar(False)
        imposto = self.economy.arrecadar(rep.atendimento)
        self.ciclo += 1
        self.random_events.avancar()
        self.bus.publish(ev.CYCLE_ADVANCED, ciclo=self.ciclo, imposto=imposto)
        return self.horario_pico() if pico else None

    def horario_pico(self) -> RushResult:
        rep = self.analisar(True)
        status = ("sucesso" if rep.fluxo_maximo >= rep.demanda else
                  "congestionada" if rep.atendimento >= 0.7 else "travou")
        bonus = 0.0
        if status == "sucesso":
            bonus = round(rep.demanda * 0.5)
            self.treasury.receber(bonus, "bonus de pico")
        res = RushResult(rep, status, bonus)
        self.bus.publish(ev.RUSH_FINISHED, resultado=res)
        return res
