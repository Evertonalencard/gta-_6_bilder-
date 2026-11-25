"""Entidades do dominio. Cada uma e especialista na propria informacao (Information Expert)."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from . import config as cfg
from .road_state import NormalState, RoadState

EdgeKey = Tuple[int, str]          # (id_da_via, "fw" | "bw")


class LotKind(Enum):
    CASA = ("casa", "casas", 500)
    COMERCIO = ("comercio", "comercios", 800)
    INDUSTRIA = ("industria", "industrias", 1200)

    def __init__(self, rotulo, campo, custo):
        self.rotulo, self.campo, self.custo = rotulo, campo, custo


class RoadKind(Enum):
    RUA = ("rua", 400, (1, 2), 800)
    AVENIDA = ("avenida", 1600, (2, 4), 1800)

    def __init__(self, rotulo, capacidade_base, faixas, custo_faixa):
        self.rotulo, self.capacidade_base, self.faixas, self.custo_faixa = (
            rotulo, capacidade_base, faixas, custo_faixa
        )


# degraus de melhoria em ordem crescente de capacidade
UPGRADE_LADDER: List[Tuple[RoadKind, int]] = [
    (RoadKind.RUA, 1), (RoadKind.RUA, 2), (RoadKind.AVENIDA, 2), (RoadKind.AVENIDA, 4)]


@dataclass
class Node:
    id: int
    nome: str
    x: float                      # coordenadas normalizadas do mapa (0..1)
    y: float
    casas: int = 0
    comercios: int = 0
    industrias: int = 0
    estadio: bool = False
    saida: bool = False

    @property
    def populacao(self): return self.casas * cfg.HAB_POR_CASA
    @property
    def vagas(self): return self.comercios * cfg.VAGAS_COMERCIO + self.industrias * cfg.VAGAS_INDUSTRIA
    @property
    def viagens_geradas(self): return int(self.populacao * cfg.VIAGENS_POR_HAB)
    @property
    def viagens_absorvidas(self): return int(self.vagas * cfg.VIAGENS_POR_HAB)

    def lotes(self, kind: LotKind) -> int: return getattr(self, kind.campo)

    def adicionar_lote(self, kind: LotKind):
        if self.lotes(kind) >= cfg.MAX_LOTES_POR_NO:
            from .errors import GameError
            raise GameError("Limite de lotes neste cruzamento.")
        setattr(self, kind.campo, self.lotes(kind) + 1)


@dataclass
class Lot:
    id: int
    kind: LotKind
    x: float
    y: float
    width: float
    height: float
    angle: float
    road_id: int
    access_node_id: Optional[int] = None

    @property
    def populacao(self) -> int:
        return cfg.HAB_POR_CASA if self.kind is LotKind.CASA else 0

    @property
    def vagas(self) -> int:
        if self.kind is LotKind.COMERCIO:
            return cfg.VAGAS_COMERCIO
        if self.kind is LotKind.INDUSTRIA:
            return cfg.VAGAS_INDUSTRIA
        return 0


@dataclass(frozen=True)
class LotPlacement:
    kind: LotKind
    x: float
    y: float
    width: float
    height: float
    angle: float
    road_id: Optional[int]
    access_x: Optional[float]
    access_y: Optional[float]
    valid: bool
    reason: str = ""


@dataclass
class DirectedEdge:
    key: EdgeKey
    u: int
    v: int
    cap_base: int
    cap: int                      # capacidade efetiva (considera o estado da via)


@dataclass
class Road:
    id: int
    u: int
    v: int
    kind: RoadKind = RoadKind.RUA
    faixas: int = 1               # por sentido
    mao_unica: bool = False       # True: apenas u -> v
    comprimento: float = 1.0
    state: RoadState = field(default_factory=NormalState)

    @property
    def cap_base(self) -> int: return self.kind.capacidade_base

    @property
    def cap_efetiva(self) -> int: return int(self.cap_base * self.state.fator)

    def custo(self, kind=None, faixas=None, mao_unica=None) -> float:
        kind, faixas = kind or self.kind, faixas or self.faixas
        unica = self.mao_unica if mao_unica is None else mao_unica
        return kind.custo_faixa * faixas * (1 if unica else 2) * self.comprimento

    def proxima_melhoria(self) -> Optional[Tuple[RoadKind, int]]:
        atual = (self.kind, self.faixas)
        try:
            indice = UPGRADE_LADDER.index(atual)
        except ValueError:
            return None
        return UPGRADE_LADDER[indice + 1] if indice + 1 < len(UPGRADE_LADDER) else None

    def arestas(self) -> List[DirectedEdge]:
        out = [DirectedEdge((self.id, "fw"), self.u, self.v, self.cap_base, self.cap_efetiva)]
        if not self.mao_unica:
            out.append(DirectedEdge((self.id, "bw"), self.v, self.u, self.cap_base, self.cap_efetiva))
        return out

    def inverter(self): self.u, self.v = self.v, self.u


class City:
    """Agregado raiz: guarda nos e vias e responde perguntas sobre eles."""

    def __init__(self):
        self.nodes: Dict[int, Node] = {}
        self.roads: Dict[int, Road] = {}
        self.lots: Dict[int, Lot] = {}
        self._nid = self._rid = self._lid = 0

    def proximo_no_id(self): self._nid += 1; return self._nid - 1
    def proxima_via_id(self): self._rid += 1; return self._rid
    def proximo_lote_id(self): self._lid += 1; return self._lid

    def add_node(self, n: Node): self.nodes[n.id] = n; self._nid = max(self._nid, n.id + 1)
    def add_road(self, r: Road): self.roads[r.id] = r; self._rid = max(self._rid, r.id)
    def add_lot(self, lot: Lot):
        self.lots[lot.id] = lot
        self._lid = max(self._lid, lot.id)

    @property
    def populacao(self):
        return sum(n.populacao for n in self.nodes.values()) + sum(l.populacao for l in self.lots.values())
    @property
    def vagas(self):
        return sum(n.vagas for n in self.nodes.values()) + sum(l.vagas for l in self.lots.values())

    def arestas(self) -> List[DirectedEdge]:
        return [e for r in self.roads.values() for e in r.arestas()]

    def estadio(self) -> Optional[Node]: return next((n for n in self.nodes.values() if n.estadio), None)
    def saidas(self) -> List[Node]: return [n for n in self.nodes.values() if n.saida]
    def via_entre(self, a: int, b: int) -> Optional[Road]:
        return next((r for r in self.roads.values() if {r.u, r.v} == {a, b}), None)
