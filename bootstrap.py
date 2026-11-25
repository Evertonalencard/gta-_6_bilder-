"""Composition root: unico lugar que conhece as classes concretas (Injecao de Dependencia)."""
import random

from core.analysis import TrafficAnalyzer, WhatIfService
from core.controller import GameController
from core.events import EventBus
from core.factories import CityFactory, CityRepository, RoadFactory, materializar_zoneamento_legado
from core.services import EconomyService, RandomEventService, RoadService, ZoningService
from core.strategies import BFSPaths, DFSPaths
from core.treasury import Treasury


def build_controller(
    mapa_json=None, usar_dfs=False, seed=None, terrain_validator=None,
    map_size=(3520, 4820),
):
    bus = EventBus()
    roads_factory = RoadFactory()
    city = CityRepository(mapa_json).carregar() if mapa_json else CityFactory(roads_factory).key_lento()
    materializar_zoneamento_legado(
        city, map_size[0], map_size[1], terrain_validator
    )
    treasury = Treasury(bus)
    road_service = RoadService(city, treasury, bus, roads_factory)
    analyzer = TrafficAnalyzer(DFSPaths() if usar_dfs else BFSPaths())
    return GameController(
        city, treasury, bus,
        ZoningService(city, treasury, bus, road_service, terrain_validator),
        road_service,
        EconomyService(city, treasury),
        RandomEventService(city, bus, random.Random(seed)),
        analyzer, WhatIfService(analyzer))
