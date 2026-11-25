"""Analise de fluxo maximo, diagnostico de gargalos e cenarios "E se?" (requisitos do PDF)."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import config as cfg
from .demand import Demand
from .domain import City, EdgeKey
from .errors import GameError
from .flow import FlowNetwork
from .strategies import AugmentingPathStrategy

S, T = "__S__", "__T__"


@dataclass
class EdgeReport:
    key: EdgeKey
    u: int
    v: int
    cap: int
    cap_base: int
    flow: int
    cor: str

    @property
    def residual(self): return self.cap - self.flow
    @property
    def utilizacao(self): return self.flow / self.cap if self.cap else 1.0
    @property
    def saturada(self): return self.cap > 0 and self.flow == self.cap


@dataclass
class FlowReport:
    fluxo_maximo: int
    demanda: int
    arestas: List[EdgeReport] = field(default_factory=list)
    corte_minimo: List[EdgeReport] = field(default_factory=list)
    aumentos: int = 0

    @property
    def atendimento(self): return self.fluxo_maximo / self.demanda if self.demanda else 1.0
    @property
    def saturadas(self): return [e for e in self.arestas if e.saturada]
    def por_chave(self): return {e.key: e for e in self.arestas}


def classificar(util: float, cap: int) -> str:
    if cap == 0: return "cinza"
    if util < cfg.LIMIAR_VERDE: return "verde"
    if util < cfg.LIMIAR_AMARELO: return "amarelo"
    return "vermelho"


class TrafficAnalyzer:
    def __init__(self, path_strategy: AugmentingPathStrategy):
        self.path_strategy = path_strategy

    def _rede(self, city: City, demand: Demand, overrides: Dict[EdgeKey, int]):
        net = FlowNetwork()
        for e in city.arestas():
            cap = overrides.get(e.key, e.cap)
            if cap > 0:
                net.add_edge(e.u, e.v, cap, e.key)
        for n, d in demand.fontes.items(): net.add_edge(S, n, d)
        for n, c in demand.sorvedouros.items(): net.add_edge(n, T, c)
        return net

    def analisar(self, city, demand, overrides=None, detalhar=True) -> FlowReport:
        overrides = overrides or {}
        net = self._rede(city, demand, overrides)
        fluxo, aug = net.max_flow(S, T, self.path_strategy)
        rep = FlowReport(fluxo, demand.total, aumentos=aug)
        if not detalhar:
            return rep
        por_key = {e.key: e for _, e in net.forward_edges()}
        for ed in city.arestas():
            e = por_key.get(ed.key)
            cap, f = (e.cap, e.flow) if e else (0, 0)
            util = f / cap if cap else 1.0
            rep.arestas.append(EdgeReport(ed.key, ed.u, ed.v, cap, ed.cap_base, f, classificar(util, cap)))
        lado_s = net.reachable_from(S)
        rep.corte_minimo = [e for e in rep.arestas if e.u in lado_s and e.v not in lado_s and e.cap > 0]
        return rep


@dataclass
class ScenarioAResult:
    via: int
    modo: str
    fluxo_antes: int
    fluxo_depois: int

    @property
    def perda(self): return self.fluxo_antes - self.fluxo_depois
    @property
    def perda_percentual(self): return 100 * self.perda / self.fluxo_antes if self.fluxo_antes else 0.0


@dataclass
class UpgradeOption:
    key: EdgeKey
    cap_atual: int
    cap_nova: int
    fluxo_novo: int
    ganho: int


class WhatIfService:
    """Cenarios A (obra/acidente) e B (investimento) do PDF."""

    FATORES = {"interditar": 0.0, "faixa": 0.5}

    def __init__(self, analyzer: TrafficAnalyzer):
        self.analyzer = analyzer

    def cenario_a(self, city, demand, road_id, modo) -> ScenarioAResult:
        if modo not in self.FATORES:
            raise GameError("modo deve ser 'interditar' ou 'faixa'.")
        road = city.roads.get(road_id)
        if not road:
            raise GameError("Via inexistente.")
        antes = self.analyzer.analisar(city, demand, detalhar=False).fluxo_maximo
        ov = {e.key: int(road.cap_base * self.FATORES[modo]) for e in road.arestas()}
        depois = self.analyzer.analisar(city, demand, ov, detalhar=False).fluxo_maximo
        return ScenarioAResult(road_id, modo, antes, depois)

    def cenario_b(self, city, demand, x: int):
        base = self.analyzer.analisar(city, demand)
        opcoes = []
        for e in base.saturadas:
            novo = self.analyzer.analisar(city, demand, {e.key: e.cap + x}, detalhar=False).fluxo_maximo
            opcoes.append(UpgradeOption(e.key, e.cap, e.cap + x, novo, novo - base.fluxo_maximo))
        opcoes.sort(key=lambda o: o.ganho, reverse=True)
        melhor: Optional[UpgradeOption] = opcoes[0] if opcoes and opcoes[0].ganho > 0 else None
        return base.fluxo_maximo, opcoes, melhor
