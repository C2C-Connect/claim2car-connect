"""pgRouting-backed dispatch routing (Slice 7; runs inside PostGIS).

The PgRoutingEngine implements the same RoutingEngine interface as the
in-memory engine, executing pgr_dijkstra, pgr_ksp, and pgr_drivingDistance
against the dispatch.network_* tables installed by the routing migration
stream (routing_migrations/). Parity with the in-memory engine is enforced by
tests in CI: same network, same queries, same answers.

Credentials and network are synthetic-only in every environment this module
runs in today. The engine never contacts an external service.
"""
from __future__ import annotations

import os
from typing import Optional

import psycopg

from app.dispatch_routing import (
    NetworkEdge,
    NetworkNode,
    Reachability,
    RoadNetwork,
    Route,
    RoutingEngine,
    RoutingError,
)

DISPATCH_SCHEMA = "dispatch"


class PgRoutingEngine(RoutingEngine):
    """Executes routing SQL inside PostGIS. One connection per engine."""

    def __init__(self, conn: psycopg.Connection):
        if conn is None or getattr(conn, "closed", True):
            raise RoutingError("INVALID_CONNECTION")
        self.conn = conn

    # --- network installation ------------------------------------------------

    def install_network(self, network: RoadNetwork, replace: bool = True) -> None:
        """Load a road network into dispatch.network_nodes/_edges.

        The whole load runs in one transaction: a partial network is never
        visible to routing queries."""
        if not isinstance(network, RoadNetwork):
            raise RoutingError("INVALID_NETWORK")
        with self.conn.transaction():
            if replace:
                self.conn.execute("DELETE FROM dispatch.network_edges")
                self.conn.execute("DELETE FROM dispatch.network_nodes")
            for node in network.nodes:
                self.conn.execute(
                    "INSERT INTO dispatch.network_nodes(node_id, label, lon, lat) VALUES (%s,%s,%s,%s)",
                    (node.node_id, node.label, node.lon, node.lat),
                )
            for edge in network.edges:
                self.conn.execute(
                    "INSERT INTO dispatch.network_edges(edge_id, source, target, cost_minutes, reverse_cost_minutes)"
                    " VALUES (%s,%s,%s,%s,%s)",
                    (edge.edge_id, edge.source, edge.target, edge.cost_minutes, edge.reverse_cost_minutes),
                )

    # --- queries ---------------------------------------------------------------

    def route(self, network: RoadNetwork, origin: int, destination: int, k: int = 1) -> tuple[Route, ...]:
        if origin not in {n.node_id for n in network.nodes} or destination not in {n.node_id for n in network.nodes}:
            raise RoutingError("UNKNOWN_NODE")
        if type(k) is not int or k < 1 or k > 5:
            raise RoutingError("INVALID_K")
        if origin == destination:
            raise RoutingError("SAME_ORIGIN_DESTINATION")
        # Directed edges SQL: one row per direction; reverse cost None -> one-way.
        edges_sql = (
            "SELECT edge_id AS id, source, target, cost_minutes AS cost FROM dispatch.network_edges "
            "UNION ALL "
            "SELECT edge_id, target, source, reverse_cost_minutes FROM dispatch.network_edges "
            "WHERE reverse_cost_minutes IS NOT NULL"
        )
        if k == 1:
            rows = self.conn.execute(
                "SELECT * FROM pgr_dijkstra(%s, %s, %s, directed := true)",
                (edges_sql, origin, destination),
            ).fetchall()
            if not rows:
                raise RoutingError("NO_ROUTE", f"{origin}->{destination}")
            # pgr_dijkstra (single pair): seq, path_seq, node, edge, cost, agg_cost
            rows = sorted(rows, key=lambda r: r[1])  # by path_seq
            node_path = [r[2] for r in rows]
            edge_ids = tuple(r[3] for r in rows if r[3] != -1)
            total = float(rows[-1][5])
            return (Route(origin, destination, tuple(node_path), edge_ids, total),)
        rows = self.conn.execute(
            "SELECT * FROM pgr_ksp(%s, %s, %s, %s, directed := true)",
            (edges_sql, origin, destination, k),
        ).fetchall()
        if not rows:
            raise RoutingError("NO_ROUTE", f"{origin}->{destination}")
        # pgr_ksp: seq, path_id, path_seq, node, edge, cost, agg_cost
        by_path: dict[int, list] = {}
        for r in rows:
            by_path.setdefault(r[1], []).append(r)
        routes = []
        for path_id in sorted(by_path):
            seq = sorted(by_path[path_id], key=lambda r: r[2])
            node_path = [r[3] for r in seq]
            edge_ids = tuple(r[4] for r in seq if r[4] != -1)
            total = float(seq[-1][6])
            routes.append(Route(origin, destination, tuple(node_path), edge_ids, total))
        return tuple(routes[:k])

    def reachable_within(self, network: RoadNetwork, origin: int, max_minutes: float) -> Reachability:
        if origin not in {n.node_id for n in network.nodes}:
            raise RoutingError("UNKNOWN_NODE")
        if not isinstance(max_minutes, (int, float)) or max_minutes < 0:
            raise RoutingError("INVALID_BUDGET")
        edges_sql = (
            "SELECT edge_id AS id, source, target, cost_minutes AS cost FROM dispatch.network_edges "
            "UNION ALL "
            "SELECT edge_id, target, source, reverse_cost_minutes FROM dispatch.network_edges "
            "WHERE reverse_cost_minutes IS NOT NULL"
        )
        rows = self.conn.execute(
            "SELECT * FROM pgr_drivingDistance(%s, %s, %s, directed := true)",
            (edges_sql, origin, float(max_minutes)),
        ).fetchall()
        # pgr_drivingDistance: seq, node, edge, cost, agg_cost
        costs = {int(r[1]): float(r[4]) for r in rows}
        reachable = tuple(sorted(costs))
        return Reachability(origin, reachable, costs)


def routing_connection() -> psycopg.Connection:
    """Synthetic-only routing database connection (CI compose service)."""
    url = os.environ.get(
        "ROUTING_DATABASE_URL",
        "postgresql://faos_app:synthetic-app-only@127.0.0.1:55433/claim2car_routing_test",
    )
    return psycopg.connect(url, connect_timeout=5)
