import unittest

from core.domain import City, LotKind, Node, RoadKind
from core.errors import InsufficientFunds
from core.events import EventBus
from core.factories import (
    CityFactory,
    RoadFactory,
    materializar_zoneamento_legado,
)
from core.services import RoadService, ZoningService
from core.treasury import Treasury


class RoadInteractionTests(unittest.TestCase):
    def setUp(self):
        self.city = City()
        for node in (
            Node(0, "a", 0.1, 0.5),
            Node(1, "b", 0.9, 0.5),
            Node(2, "c", 0.5, 0.1),
            Node(3, "d", 0.5, 0.9),
        ):
            self.city.add_node(node)
        self.bus = EventBus()
        self.treasury = Treasury(self.bus, saldo=1_000_000)
        self.roads = RoadService(self.city, self.treasury, self.bus, RoadFactory())

    def test_crossing_road_building_creates_and_connects_intersection(self):
        self.roads.construir(0, 1, RoadKind.RUA, 1, False)
        self.roads.construir(2, 3, RoadKind.RUA, 1, False)

        center = next(
            node for node in self.city.nodes.values()
            if abs(node.x - 0.5) < 1e-8 and abs(node.y - 0.5) < 1e-8
        )
        self.assertEqual(len(self.city.roads), 4)
        self.assertEqual(
            sum(center.id in (road.u, road.v) for road in self.city.roads.values()),
            4,
        )

    def test_capacity_is_fixed_by_road_kind_not_lane_count(self):
        street_one = self.roads.construir(0, 1, RoadKind.RUA, 1, False)
        street_two = self.roads.construir(2, 3, RoadKind.RUA, 2, False)
        avenue_two = self.roads.construir(0, 2, RoadKind.AVENIDA, 2, False)
        avenue_four = self.roads.construir(1, 3, RoadKind.AVENIDA, 4, False)

        self.assertEqual(street_one.cap_base, 400)
        self.assertEqual(street_two.cap_base, 400)
        self.assertEqual(avenue_two.cap_base, 1600)
        self.assertEqual(avenue_four.cap_base, 1600)

    def test_large_lot_is_validated_connected_and_counted(self):
        self.roads.construir(0, 1, RoadKind.RUA, 1, False)
        zoning = ZoningService(self.city, self.treasury, self.bus, self.roads)
        placement = zoning.previsualizar(1760, 2410, LotKind.CASA, 3520, 4820)
        self.assertTrue(placement.valid, placement.reason)

        lot = zoning.colocar(placement, 3520, 4820)
        self.assertEqual((lot.width, lot.height), (placement.width, placement.height))
        self.assertEqual(lot.populacao, 15)
        self.assertEqual(self.city.populacao, 15)
        self.assertIsNotNone(lot.access_node_id)

    def test_lot_preview_rejects_water_and_overlap(self):
        self.roads.construir(0, 1, RoadKind.RUA, 1, False)
        water_zoning = ZoningService(
            self.city, self.treasury, self.bus, self.roads,
            land_validator=lambda _x, _y: False,
        )
        water = water_zoning.previsualizar(1760, 2410, LotKind.CASA, 3520, 4820)
        self.assertFalse(water.valid)
        self.assertIn("agua", water.reason)

        zoning = ZoningService(self.city, self.treasury, self.bus, self.roads)
        first = zoning.previsualizar(1760, 2410, LotKind.CASA, 3520, 4820)
        zoning.colocar(first, 3520, 4820)
        overlap = zoning.previsualizar(1760, 2410, LotKind.CASA, 3520, 4820)
        self.assertFalse(overlap.valid)

    def test_road_snap_and_demolition_update_city(self):
        self.roads.construir(0, 1, RoadKind.RUA, 1, False)
        node = self.roads.criar_cruzamento_na_via(1, 0.4, 0.5)
        zoning = ZoningService(self.city, self.treasury, self.bus)
        zoning.construir(node.id, LotKind.CASA)
        self.assertEqual(node.casas, 1)

        zoning.demolir(node.id, LotKind.CASA)
        self.roads.demolir(1)
        self.assertEqual(node.casas, 0)
        self.assertNotIn(1, self.city.roads)
        self.assertEqual(len(self.city.roads), 1)

    def test_failed_drag_build_removes_uncommitted_endpoints(self):
        self.treasury.saldo = 0

        with self.assertRaises(InsufficientFunds):
            self.roads.construir_por_coordenadas(
                0.2, 0.2, 0.8, 0.8, RoadKind.RUA, 1, False
            )

        self.assertEqual(set(self.city.nodes), {0, 1, 2, 3})
        self.assertEqual(self.city.roads, {})

    def test_initial_legacy_zones_are_migrated_to_visible_lots_once(self):
        city = CityFactory(RoadFactory()).key_lento()

        materializar_zoneamento_legado(city, 3520, 4820, lambda _x, _y: True)
        lot_count = len(city.lots)

        self.assertGreater(lot_count, 0)
        self.assertEqual(
            sum(node.casas + node.comercios + node.industrias for node in city.nodes.values()),
            0,
        )
        self.assertGreater(city.populacao, 0)
        self.assertGreater(city.vagas, 0)
        materializar_zoneamento_legado(city, 3520, 4820, lambda _x, _y: True)
        self.assertEqual(len(city.lots), lot_count)


if __name__ == "__main__":
    unittest.main()
