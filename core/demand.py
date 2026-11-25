"""Strategy: de onde saem e para onde vao os veiculos."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict

from . import config as cfg
from .domain import City
from .errors import GameError


@dataclass(frozen=True)
class Demand:
    fontes: Dict[int, int]          # no -> veiculos/h gerados
    sorvedouros: Dict[int, int]     # no -> veiculos/h absorvidos

    @property
    def total(self): return sum(self.fontes.values())


class DemandStrategy(ABC):
    @abstractmethod
    def build(self, city: City) -> Demand: ...


class CommuteDemand(DemandStrategy):
    """Rotina: casas geram viagens, comercio/industria sao os destinos de cada habitante."""

    def build(self, city):
        f = {n.id: n.viagens_geradas for n in city.nodes.values() if n.casas}
        s = {n.id: n.viagens_absorvidas for n in city.nodes.values() if n.vagas}
        for lot in city.lots.values():
            if lot.access_node_id is None:
                continue
            if lot.populacao:
                f[lot.access_node_id] = f.get(lot.access_node_id, 0) + int(
                    lot.populacao * cfg.VIAGENS_POR_HAB
                )
            if lot.vagas:
                s[lot.access_node_id] = s.get(lot.access_node_id, 0) + int(
                    lot.vagas * cfg.VIAGENS_POR_HAB
                )
        return Demand(f, s)


class StadiumEventDemand(DemandStrategy):
    """Horario de pico: saida de um grande evento no estadio rumo as saidas da cidade."""

    def __init__(self, veiculos: int):
        self.veiculos = veiculos

    def build(self, city):
        est, saidas = city.estadio(), city.saidas()
        if not est or not saidas:
            raise GameError("O mapa precisa de um estadio e ao menos uma saida.")
        return Demand({est.id: self.veiculos}, {s.id: cfg.INFINITO for s in saidas})
