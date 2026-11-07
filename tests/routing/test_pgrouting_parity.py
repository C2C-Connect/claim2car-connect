"""
pgRouting parity tests (Slice 7; requires the routing database service).

The PgRoutingEngine must answer identically to the in-memory reference
engine on the shared synthetic network: same shortest paths, same costs,
same k-shortest sets, same reachability. Any divergence is a routing bug in
whichever engine disagrees with the reference.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import psycopg

from app.dispatch_routing import InMemoryRoutingEngine, RoutingError, load_road_network
from database.dispatch_routing import PgRoutingEngine

DEPOT_LABEL, INCIDENT_LABEL, SHOP_LABEL, DEALER_LABEL = (
    "operator-depot", "incident-scene", "shop-a", "dealer-c"
)


class TestPgRoutingParity(unittest.TestCase):
    """Skips automatically (setUpClass) when the routing database is unavailable."""
    @classmethod
    def setUpClass(cls):
        url = os.environ.get(
            "ROUTING_DATABASE_URL",
            "postgresql://faos_app:synthetic-app-only@127.0.0.1:55433/claim2car_routing_test",
        )
        try:
            cls.conn = psycopg.connect(url, connect_timeout=5)
        except psycopg.OperationalError:
            raise unittest.SkipTest("routing database unavailable")
        cls.network = load_road_network()
        cls.engine = PgRoutingEngine(cls.conn)
        cls.engine.install_network(cls.network)
        cls.reference = InMemoryRoutingEngine()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "conn"):
            cls.conn.close()

    def node(self, label):
        return self.network.node_by_label(label).node_id

    def test_extension_and_schema_installed(self):
        ext = self.conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'pgrouting'"
        ).fetchone()
        self.assertIsNotNone(ext)
        tables = self.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'dispatch'"
        ).fetchall()
        self.assertIn("network_nodes", {t[0] for t in tables})
        self.assertIn("network_edges", {t[0] for t in tables})
        counts = self.conn.execute("SELECT (SELECT count(*) FROM dispatch.network_nodes), (SELECT count(*) FROM dispatch.network_edges)").fetchone()
        self.assertEqual(counts, (len(self.network.nodes), len(self.network.edges)))

    def test_shortest_path_parity_depot_to_incident(self):
        got = self.engine.route(self.network, self.node(DEPOT_LABEL), self.node(INCIDENT_LABEL))[0]
        want = self.reference.route(self.network, self.node(DEPOT_LABEL), self.node(INCIDENT_LABEL))[0]
        self.assertEqual(got.node_path, want.node_path)
        self.assertEqual(got.edge_ids, want.edge_ids)
        self.assertAlmostEqual(got.total_cost_minutes, want.total_cost_minutes, places=6)

    def test_shortest_path_parity_incident_to_shop(self):
        got = self.engine.route(self.network, self.node(INCIDENT_LABEL), self.node(SHOP_LABEL))[0]
        want = self.reference.route(self.network, self.node(INCIDENT_LABEL), self.node(SHOP_LABEL))[0]
        self.assertEqual(got.node_path, want.node_path)
        self.assertAlmostEqual(got.total_cost_minutes, want.total_cost_minutes, places=6)

    def test_shortest_path_parity_incident_to_dealer(self):
        got = self.engine.route(self.network, self.node(INCIDENT_LABEL), self.node(DEALER_LABEL))[0]
        want = self.reference.route(self.network, self.node(INCIDENT_LABEL), self.node(DEALER_LABEL))[0]
        self.assertEqual(got.node_path, want.node_path)
        self.assertAlmostEqual(got.total_cost_minutes, want.total_cost_minutes, places=6)

    def test_k_shortest_parity(self):
        got = self.engine.route(self.network, self.node(DEPOT_LABEL), self.node(INCIDENT_LABEL), k=3)
        want = self.reference.route(self.network, self.node(DEPOT_LABEL), self.node(INCIDENT_LABEL), k=3)
        self.assertEqual(len(got), len(want))
        for g, w in zip(got, want):
            self.assertEqual(g.node_path, w.node_path)
            self.assertAlmostEqual(g.total_cost_minutes, w.total_cost_minutes, places=6)

    def test_reachability_parity(self):
        got = self.engine.reachable_within(self.network, self.node(DEPOT_LABEL), 8.0)
        want = self.reference.reachable_within(self.network, self.node(DEPOT_LABEL), 8.0)
        self.assertEqual(got.reachable, want.reachable)
        for node in want.reachable:
            self.assertAlmostEqual(got.costs[node], want.costs[node], places=6)

    def test_reachability_whole_grid(self):
        got = self.engine.reachable_within(self.network, self.node(DEPOT_LABEL), 60.0)
        self.assertEqual(len(got.reachable), len(self.network.nodes))

    def test_unknown_node_rejected(self):
        with self.assertRaises(RoutingError):
            self.engine.route(self.network, 999, 1)

    def test_one_way_semantics_parity(self):
        """Routing upward through the one-way edge must detour in both engines."""
        # One-way edge: node 21 -> 27 (downward only).
        got = self.engine.route(self.network, 27, 21)[0]
        want = self.reference.route(self.network, 27, 21)[0]
        self.assertEqual(got.node_path, want.node_path)
        self.assertNotIn((27, 21), list(zip(got.node_path, got.node_path[1:])))
