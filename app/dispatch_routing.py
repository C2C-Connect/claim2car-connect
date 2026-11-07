"""Tow dispatch routing and navigation handoff (Slice 7; CTO brief Tier 1 #3).

Implements the acceptance → tow dispatch → navigation chain of product
contract §7 on a road-network graph. Ordering rule from plan v1.3 §3.2 is
enforced structurally: NO dispatch is planned until the receiving party
(shop or dealer) has a recorded acceptance — acceptance precedes tow
dispatch, always.

Two engines implement one interface:
- InMemoryRoutingEngine — pure Python (Dijkstra, Yen k-shortest, driving
  distance frontier); deterministic; runs anywhere; used by the controlled
  demonstration and offline tests.
- database.dispatch_routing.PgRoutingEngine — the same queries executed by
  pgRouting inside PostGIS (pgr_dijkstra, pgr_ksp, pgr_drivingDistance);
  verified against the in-memory engine by parity tests in CI.

Navigation handoff (D-13 open): provider-selectable deep links are built
from the planned route's coordinates. No provider is contacted — the link
is handed to the driver's device. Provider choice remains an owner
decision; the registry makes swapping providers a one-line change.
"""
from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

NETWORK_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "synthetic-road-network.json"
NETWORK_SCHEMA_VERSION = "0.1"

PROVIDER_GOOGLE = "google"
PROVIDER_APPLE = "apple"
PROVIDER_OSRM_DEMO = "osrm-demo"
NAVIGATION_PROVIDERS = frozenset({PROVIDER_GOOGLE, PROVIDER_APPLE, PROVIDER_OSRM_DEMO})
# OSRM's public demo server is for development only — never production routing.
OSRM_DEMO_URI_PREFIX = "https://router.project-osrm.org/route/v1/driving/"


class RoutingError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


# --- network contract -------------------------------------------------------

@dataclass(frozen=True)
class NetworkNode:
    node_id: int
    label: str
    lon: float
    lat: float


@dataclass(frozen=True)
class NetworkEdge:
    edge_id: int
    source: int
    target: int
    cost_minutes: float
    reverse_cost_minutes: Optional[float]  # None = one-way


@dataclass(frozen=True)
class RoadNetwork:
    network_id: str
    version: str
    nodes: tuple[NetworkNode, ...]
    edges: tuple[NetworkEdge, ...]

    def node(self, node_id: int) -> NetworkNode:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        raise RoutingError("UNKNOWN_NODE", str(node_id))

    def node_by_label(self, label: str) -> NetworkNode:
        for n in self.nodes:
            if n.label == label:
                return n
        raise RoutingError("UNKNOWN_NODE_LABEL", label)


def load_road_network(path: Path = NETWORK_CONTRACT_PATH) -> RoadNetwork:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        type(value) is not dict
        or value.get("schema_version") != NETWORK_SCHEMA_VERSION
        or not isinstance(value.get("network_id"), str)
        or not value["network_id"].strip()
        or not isinstance(value.get("version"), str)
        or type(value.get("nodes")) is not list
        or not value["nodes"]
        or type(value.get("edges")) is not list
        or not value["edges"]
    ):
        raise RoutingError("INVALID_NETWORK_CONTRACT")
    nodes, seen_ids, seen_labels = [], set(), set()
    for n in value["nodes"]:
        if (
            type(n) is not dict
            or set(n) != {"node_id", "label", "lon", "lat"}
            or type(n["node_id"]) is not int
            or not isinstance(n["label"], str)
            or not n["label"].strip()
            or not isinstance(n["lon"], (int, float))
            or not isinstance(n["lat"], (int, float))
            or not (-180 <= n["lon"] <= 180)
            or not (-90 <= n["lat"] <= 90)
        ):
            raise RoutingError("INVALID_NETWORK_NODE")
        if n["node_id"] in seen_ids or n["label"] in seen_labels:
            raise RoutingError("DUPLICATE_NODE")
        seen_ids.add(n["node_id"])
        seen_labels.add(n["label"])
        nodes.append(NetworkNode(n["node_id"], n["label"], float(n["lon"]), float(n["lat"])))
    node_ids = seen_ids
    edges, edge_ids = [], set()
    for e in value["edges"]:
        if (
            type(e) is not dict
            or set(e) != {"edge_id", "source", "target", "cost_minutes", "reverse_cost_minutes"}
            or type(e["edge_id"]) is not int
            or type(e["source"]) is not int
            or type(e["target"]) is not int
            or not isinstance(e["cost_minutes"], (int, float))
            or e["cost_minutes"] <= 0
            or not (e["reverse_cost_minutes"] is None or (isinstance(e["reverse_cost_minutes"], (int, float)) and e["reverse_cost_minutes"] > 0))
            or e["source"] not in node_ids
            or e["target"] not in node_ids
            or e["source"] == e["target"]
        ):
            raise RoutingError("INVALID_NETWORK_EDGE")
        if e["edge_id"] in edge_ids:
            raise RoutingError("DUPLICATE_EDGE")
        edge_ids.add(e["edge_id"])
        edges.append(
            NetworkEdge(e["edge_id"], e["source"], e["target"], float(e["cost_minutes"]),
                        None if e["reverse_cost_minutes"] is None else float(e["reverse_cost_minutes"]))
        )
    return RoadNetwork(value["network_id"], value["version"], tuple(nodes), tuple(edges))


# --- routing engines ---------------------------------------------------------

@dataclass(frozen=True)
class Route:
    origin: int
    destination: int
    node_path: tuple[int, ...]
    edge_ids: tuple[int, ...]
    total_cost_minutes: float

    def waypoints(self, network: RoadNetwork) -> tuple[tuple[float, float], ...]:
        return tuple((network.node(n).lon, network.node(n).lat) for n in self.node_path)


@dataclass(frozen=True)
class Reachability:
    origin: int
    reachable: tuple[int, ...]  # nodes reachable within the budget, sorted
    costs: dict  # node_id -> cost_minutes


class RoutingEngine:
    """Interface shared by the in-memory and pgRouting implementations."""

    def route(self, network: RoadNetwork, origin: int, destination: int, k: int = 1) -> tuple[Route, ...]:
        raise NotImplementedError

    def reachable_within(self, network: RoadNetwork, origin: int, max_minutes: float) -> Reachability:
        raise NotImplementedError


class InMemoryRoutingEngine(RoutingEngine):
    """Deterministic pure-Python routing: Dijkstra, Yen k-shortest paths, and a
    driving-distance frontier. Tie-breaks on node id so results are stable."""

    def _adjacency(self, network: RoadNetwork):
        adj = {n.node_id: [] for n in network.nodes}
        for e in network.edges:
            adj[e.source].append((e.target, e.cost_minutes, e.edge_id))
            if e.reverse_cost_minutes is not None:
                adj[e.target].append((e.source, e.reverse_cost_minutes, e.edge_id))
        return adj

    def _dijkstra(self, adj, origin, stop_at=None):
        dist = {origin: 0.0}
        prev = {}  # node -> (previous node, edge_id)
        heap = [(0.0, origin)]
        visited = set()
        while heap:
            cost, node = heapq.heappop(heap)
            if node in visited:
                continue
            visited.add(node)
            if stop_at is not None and node == stop_at:
                break
            for neighbor, weight, edge_id in adj.get(node, ()):
                candidate = cost + weight
                if neighbor not in dist or candidate < dist[neighbor] - 1e-12:
                    dist[neighbor] = candidate
                    prev[neighbor] = (node, edge_id)
                    heapq.heappush(heap, (candidate, neighbor))
        return dist, prev

    def _reconstruct(self, origin, destination, prev):
        path, node = [], destination
        while node != origin:
            if node not in prev:
                raise RoutingError("NO_ROUTE", f"{origin}->{destination}")
            path.append(node)
            node = prev[node][0]
        path.append(origin)
        path.reverse()
        edges = tuple(prev[n][1] for n in path[1:])
        return tuple(path), edges

    def route(self, network: RoadNetwork, origin: int, destination: int, k: int = 1) -> tuple[Route, ...]:
        if origin not in {n.node_id for n in network.nodes} or destination not in {n.node_id for n in network.nodes}:
            raise RoutingError("UNKNOWN_NODE")
        if type(k) is not int or k < 1 or k > 5:
            raise RoutingError("INVALID_K")
        if origin == destination:
            raise RoutingError("SAME_ORIGIN_DESTINATION")
        adj = self._adjacency(network)
        dist, prev = self._dijkstra(adj, origin, stop_at=destination)
        if destination not in dist:
            raise RoutingError("NO_ROUTE", f"{origin}->{destination}")
        best_path, best_edges = self._reconstruct(origin, destination, prev)
        if k == 1:
            return (Route(origin, destination, best_path, best_edges, dist[destination]),)
        # Yen's algorithm for k shortest simple paths.
        accepted = [Route(origin, destination, best_path, best_edges, dist[destination])]
        candidates = []  # (cost, path, edges)
        seen_paths = {best_path}
        for _ in range(k - 1):
            for i in range(len(best_path) - 1):
                spur_node, root_path = best_path[i], best_path[: i + 1]
                root_edges = tuple(best_edges[:i]) if i else ()
                root_cost = sum(
                    w for (a, b) in zip(root_path, root_path[1:])
                    for (t, w, _) in adj.get(a, ()) if t == b
                )
                removed_edges = set()
                for route_ in accepted:
                    if route_.node_path[: i + 1] == root_path:
                        removed_edges.add(route_.edge_ids[i])
                spur_dist, spur_prev = self._dijkstra(
                    {n: [x for x in adj.get(n, ()) if x[2] not in removed_edges] for n in adj},
                    spur_node,
                    stop_at=destination,
                )
                if destination in spur_dist and destination not in root_path[1:]:
                    spur_path, spur_edges = self._reconstruct(spur_node, destination, spur_prev)
                    total_path = root_path[:-1] + spur_path if root_path else spur_path
                    if len(set(total_path)) != len(total_path):
                        continue
                    total_edges = root_edges + spur_edges
                    total_cost = root_cost + spur_dist[destination]
                    if total_path not in seen_paths:
                        heapq.heappush(candidates, (round(total_cost, 9), total_path, total_edges))
                        seen_paths.add(total_path)
            if not candidates:
                break
            _, best_path, best_edges = heapq.heappop(candidates)
            accepted.append(Route(origin, destination, best_path, best_edges, self._path_cost(adj, best_path)))
            if len(accepted) >= k:
                break
        return tuple(accepted)

    def _path_cost(self, adj, path):
        total = 0.0
        for a, b in zip(path, path[1:]):
            options = [w for (t, w, _) in adj.get(a, ()) if t == b]
            if not options:
                raise RoutingError("NO_ROUTE")
            total += min(options)
        return total

    def reachable_within(self, network: RoadNetwork, origin: int, max_minutes: float) -> Reachability:
        if origin not in {n.node_id for n in network.nodes}:
            raise RoutingError("UNKNOWN_NODE")
        if not isinstance(max_minutes, (int, float)) or max_minutes < 0:
            raise RoutingError("INVALID_BUDGET")
        adj = self._adjacency(network)
        dist, _ = self._dijkstra(adj, origin)
        reachable = tuple(sorted(n for n, c in dist.items() if c <= max_minutes + 1e-9))
        costs = {n: c for n, c in dist.items() if c <= max_minutes + 1e-9}
        return Reachability(origin, reachable, costs)


# --- navigation handoff (D-13 open: provider-selectable, no provider contact) ---

@dataclass(frozen=True)
class NavigationHandoff:
    provider: str
    uri: str
    label: str


class NavigationHandoffBuilder:
    """Builds provider deep links from a planned route. No network calls."""

    def __init__(self, allowed_providers=frozenset(NAVIGATION_PROVIDERS)):
        self.allowed_providers = frozenset(allowed_providers)

    def handoff(self, provider: str, route: Route, network: RoadNetwork, label: str = "") -> NavigationHandoff:
        if provider not in self.allowed_providers:
            raise RoutingError("UNKNOWN_NAVIGATION_PROVIDER", provider)
        points = route.waypoints(network)
        if not points:
            raise RoutingError("EMPTY_ROUTE")
        label = label or f"{network.node(route.origin).label} -> {network.node(route.destination).label}"
        if provider == PROVIDER_GOOGLE:
            origin = f"{points[0][1]},{points[0][0]}"
            destination = f"{points[-1][1]},{points[-1][0]}"
            waypoints = "|".join(f"{lat},{lon}" for lon, lat in points[1:-1])
            uri = (
                f"https://www.google.com/maps/dir/?api=1&origin={origin}"
                f"&destination={destination}"
                + (f"&waypoints={waypoints}" if waypoints else "")
            )
        elif provider == PROVIDER_APPLE:
            daddr = f"{points[-1][1]},{points[-1][0]}"
            saddr = f"{points[0][1]},{points[0][0]}"
            uri = f"https://maps.apple.com/?saddr={saddr}&daddr={daddr}&dirflg=d"
        else:  # OSRM demo (development only)
            coords = ";".join(f"{lon},{lat}" for lon, lat in points)
            uri = f"{OSRM_DEMO_URI_PREFIX}{coords}?overview=false"
        return NavigationHandoff(provider, uri, label)


# --- acceptance-gated dispatch service (product contract §7) -------------------

RECEIVING_PARTY_TYPES = frozenset({"shop", "dealer"})


@dataclass(frozen=True)
class AcceptanceRecord:
    party_type: str  # shop | dealer
    party_id: str
    accepted_at: str
    location_label: str


@dataclass(frozen=True)
class DispatchPlan:
    acceptance: AcceptanceRecord
    leg_to_incident: Route  # operator origin -> incident scene
    leg_to_receiving_party: Route  # incident scene -> accepting shop/dealer
    total_cost_minutes: float
    handoffs: tuple[NavigationHandoff, ...]


class DispatchRoutingService:
    """Plans the two-leg tow dispatch. Acceptance precedes dispatch — always."""

    def __init__(self, engine: RoutingEngine, handoff_builder: Optional[NavigationHandoffBuilder] = None):
        if not isinstance(engine, RoutingEngine):
            raise RoutingError("INVALID_ENGINE")
        self.engine = engine
        self.handoff_builder = handoff_builder or NavigationHandoffBuilder()

    def plan(
        self,
        network: RoadNetwork,
        acceptance: AcceptanceRecord,
        operator_origin_label: str,
        incident_label: str,
        provider: str,
    ) -> DispatchPlan:
        if not isinstance(acceptance, AcceptanceRecord):
            raise RoutingError("INVALID_ACCEPTANCE")
        if acceptance.party_type not in RECEIVING_PARTY_TYPES:
            raise RoutingError("INVALID_PARTY_TYPE", acceptance.party_type)
        if not isinstance(acceptance.party_id, str) or not acceptance.party_id.strip():
            raise RoutingError("INVALID_PARTY_ID")
        if not isinstance(acceptance.accepted_at, str) or not acceptance.accepted_at.strip():
            raise RoutingError("INVALID_ACCEPTANCE_TIMESTAMP")
        if not isinstance(acceptance.location_label, str) or not acceptance.location_label.strip():
            raise RoutingError("INVALID_ACCEPTANCE_LOCATION")
        origin = network.node_by_label(operator_origin_label).node_id
        incident = network.node_by_label(incident_label).node_id
        destination = network.node_by_label(acceptance.location_label).node_id
        if origin == incident or incident == destination:
            raise RoutingError("DEGENERATE_DISPATCH")
        leg1 = self.engine.route(network, origin, incident, k=1)[0]
        leg2 = self.engine.route(network, incident, destination, k=1)[0]
        handoffs = (
            self.handoff_builder.handoff(provider, leg1, network, "Tow leg 1: operator to incident scene"),
            self.handoff_builder.handoff(provider, leg2, network, f"Tow leg 2: incident scene to accepting {acceptance.party_type}"),
        )
        return DispatchPlan(
            acceptance=acceptance,
            leg_to_incident=leg1,
            leg_to_receiving_party=leg2,
            total_cost_minutes=round(leg1.total_cost_minutes + leg2.total_cost_minutes, 6),
            handoffs=handoffs,
        )
