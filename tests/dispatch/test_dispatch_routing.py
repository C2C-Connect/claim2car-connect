"""
Dispatch routing tests (Slice 7; no database required).

Covers the network contract, the in-memory engine (Dijkstra, k-shortest,
driving distance, one-way and closure semantics), navigation handoff link
building (D-13 open: provider-selectable), and the acceptance-gated
dispatch service enforcing product contract §7 ordering: acceptance
precedes tow dispatch.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest

from app.dispatch_routing import (
    AcceptanceRecord,
    DispatchPlan,
    DispatchRoutingService,
    InMemoryRoutingEngine,
    NavigationHandoffBuilder,
    PROVIDER_APPLE,
    PROVIDER_GOOGLE,
    PROVIDER_OSRM_DEMO,
    RoadNetwork,
    RoutingError,
    load_road_network,
)

pytestmark = pytest.mark.subtests

DEPOT = "operator-depot"
INCIDENT = "incident-scene"
SHOP_A = "shop-a"
DEALER = "dealer-c"


@pytest.fixture(scope="module")
def network():
    return load_road_network()


@pytest.fixture(scope="module")
def engine():
    return InMemoryRoutingEngine()


# --- network contract ---------------------------------------------------------

def test_network_contract_loads(network):
    assert network.network_id == "synthetic-houston-grid-v1"
    assert len(network.nodes) == 36 and len(network.edges) == 59
    assert network.node_by_label(DEPOT).node_id == 0
    assert network.node_by_label(INCIDENT).node_id == 15
    assert network.node_by_label(SHOP_A).node_id == 25
    assert network.node_by_label(DEALER).node_id == 35


def test_network_contract_rejects_malformed(tmp_path):
    bad = tmp_path / "bad-network.json"
    bad.write_text('{"schema_version": "0.1", "network_id": "x", "version": "1", "nodes": [], "edges": []}')
    with pytest.raises(RoutingError) as e:
        load_road_network(bad)
    assert e.value.code == "INVALID_NETWORK_CONTRACT"


def test_unknown_nodes_rejected(network):
    with pytest.raises(RoutingError):
        network.node(999)
    with pytest.raises(RoutingError):
        network.node_by_label("not-a-label")


# --- in-memory engine -----------------------------------------------------------

def test_shortest_path_known_answer():
    """Tiny line network: A -2-> B -3-> C gives cost 5 and the obvious path."""
    net = RoadNetwork(
        "line", "1",
        nodes=tuple(type("N", (), {"node_id": i, "label": l, "lon": 0.0, "lat": 0.0}) for i, l in ((1, "A"), (2, "B"), (3, "C"))),
        edges=tuple(),
    )
    # Build via the JSON loader instead of ad-hoc objects for realism.
    import json

    contract = {
        "schema_version": "0.1", "network_id": "line", "version": "1",
        "nodes": [{"node_id": 1, "label": "A", "lon": 0, "lat": 0},
                  {"node_id": 2, "label": "B", "lon": 0.1, "lat": 0},
                  {"node_id": 3, "label": "C", "lon": 0.2, "lat": 0}],
        "edges": [
            {"edge_id": 1, "source": 1, "target": 2, "cost_minutes": 2.0, "reverse_cost_minutes": 2.0},
            {"edge_id": 2, "source": 2, "target": 3, "cost_minutes": 3.0, "reverse_cost_minutes": 3.0},
            {"edge_id": 3, "source": 1, "target": 3, "cost_minutes": 10.0, "reverse_cost_minutes": 10.0},
        ],
    }
    p = Path("/tmp/line-network.json")
    p.write_text(json.dumps(contract))
    net = load_road_network(p)
    route = InMemoryRoutingEngine().route(net, 1, 3)[0]
    assert route.node_path == (1, 2, 3) and route.edge_ids == (1, 2)
    assert route.total_cost_minutes == pytest.approx(5.0)


def test_shortest_path_on_grid(network, engine):
    route = engine.route(network, network.node_by_label(DEPOT).node_id, network.node_by_label(INCIDENT).node_id)[0]
    assert route.node_path[0] == 0 and route.node_path[-1] == 15
    # Grid distance lower bound: 2 rows + 3 cols at 2 min each = 10. The
    # closure at (1,3)-(2,3) (edge 19) must never be used, but an equal-length
    # alternate exists via row 2, so the optimum stays at the grid bound.
    assert route.total_cost_minutes == pytest.approx(10.0)
    assert 19 not in route.edge_ids


def test_one_way_edge_never_traversed_upward(network, engine):
    # Edge (3,3)->(4,3) is one-way downward (node 21 -> 27).
    route = engine.route(network, 27, 21)[0]
    assert route.node_path != (27, 21)
    assert 27 != route.node_path[0] or 21 != route.node_path[-1] or len(route.node_path) > 2
    # And the direct upward traversal is impossible: path must detour.
    direct_edge_used = any(a == 27 and b == 21 for a, b in zip(route.node_path, route.node_path[1:]))
    assert not direct_edge_used


def test_k_shortest_paths_distinct(network, engine):
    routes = engine.route(network, 0, 15, k=3)
    assert 2 <= len(routes) <= 3
    paths = {r.node_path for r in routes}
    assert len(paths) == len(routes)  # distinct
    costs = [r.total_cost_minutes for r in routes]
    assert costs == sorted(costs)  # non-decreasing


def test_k_bounds_validated(network, engine):
    for k in (0, -1, 6, "2"):
        with pytest.raises(RoutingError):
            engine.route(network, 0, 15, k=k)


def test_same_origin_destination_rejected(network, engine):
    with pytest.raises(RoutingError) as e:
        engine.route(network, 0, 0)
    assert e.value.code == "SAME_ORIGIN_DESTINATION"


def test_unreachable_destination(tmp_path):
    import json

    contract = {
        "schema_version": "0.1", "network_id": "split", "version": "1",
        "nodes": [{"node_id": 1, "label": "A", "lon": 0, "lat": 0},
                  {"node_id": 2, "label": "B", "lon": 1, "lat": 0},
                  {"node_id": 3, "label": "C", "lon": 2, "lat": 0}],
        "edges": [{"edge_id": 1, "source": 1, "target": 2, "cost_minutes": 1.0, "reverse_cost_minutes": 1.0}],
    }
    p = tmp_path / "split.json"
    p.write_text(json.dumps(contract))
    net = load_road_network(p)
    with pytest.raises(RoutingError) as e:
        InMemoryRoutingEngine().route(net, 1, 3)
    assert e.value.code == "NO_ROUTE"


def test_reachable_within(network, engine):
    reach = engine.reachable_within(network, 0, 4.0)
    assert 0 in reach.reachable
    # Only immediate grid neighbors (2 min) are within 4 minutes.
    assert 1 in reach.reachable and 6 in reach.reachable
    assert 35 not in reach.reachable
    reach_far = engine.reachable_within(network, 0, 60.0)
    assert len(reach_far.reachable) == 36  # whole grid reachable


# --- navigation handoff -----------------------------------------------------------

def test_google_handoff_link(network, engine):
    route = engine.route(network, 0, 15)[0]
    handoff = NavigationHandoffBuilder().handoff(PROVIDER_GOOGLE, route, network, "leg 1")
    assert handoff.uri.startswith("https://www.google.com/maps/dir/?api=1&origin=")
    assert "destination=" in handoff.uri and "waypoints=" in handoff.uri
    assert handoff.label == "leg 1"


def test_apple_and_osrm_handoff_links(network, engine):
    route = engine.route(network, 15, 25)[0]
    builder = NavigationHandoffBuilder()
    apple = builder.handoff(PROVIDER_APPLE, route, network)
    assert apple.uri.startswith("https://maps.apple.com/?saddr=") and "daddr=" in apple.uri
    osrm = builder.handoff(PROVIDER_OSRM_DEMO, route, network)
    assert osrm.uri.startswith("https://router.project-osrm.org/route/v1/driving/")


def test_unknown_provider_rejected(network, engine):
    route = engine.route(network, 0, 15)[0]
    with pytest.raises(RoutingError) as e:
        NavigationHandoffBuilder().handoff("waze", route, network)
    assert e.value.code == "UNKNOWN_NAVIGATION_PROVIDER"


# --- acceptance-gated dispatch service -----------------------------------------------

def make_acceptance(party_type="shop", location=SHOP_A):
    return AcceptanceRecord(party_type=party_type, party_id=f"{party_type}-001",
                            accepted_at="2026-11-07T10:00:00+00:00", location_label=location)


def test_dispatch_requires_acceptance_record(network):
    service = DispatchRoutingService(InMemoryRoutingEngine())
    for bad in (None, "accepted", 42):
        with pytest.raises(RoutingError):
            service.plan(network, bad, DEPOT, INCIDENT, PROVIDER_GOOGLE)


def test_dispatch_acceptance_validation(network):
    service = DispatchRoutingService(InMemoryRoutingEngine())
    good = make_acceptance()
    for mutate in (
        lambda a: a.__class__(**{**a.__dict__, "party_type": "driver"}),  # invalid party type
        lambda a: a.__class__(**{**a.__dict__, "party_id": ""}),
        lambda a: a.__class__(**{**a.__dict__, "accepted_at": ""}),
        lambda a: a.__class__(**{**a.__dict__, "location_label": "nowhere"}),
    ):
        with pytest.raises(RoutingError):
            service.plan(network, mutate(good), DEPOT, INCIDENT, PROVIDER_GOOGLE)


def test_dispatch_plan_two_legs_and_handoffs(network):
    service = DispatchRoutingService(InMemoryRoutingEngine())
    plan = service.plan(network, make_acceptance(), DEPOT, INCIDENT, PROVIDER_GOOGLE)
    assert isinstance(plan, DispatchPlan)
    assert plan.leg_to_incident.node_path[0] == network.node_by_label(DEPOT).node_id
    assert plan.leg_to_incident.node_path[-1] == network.node_by_label(INCIDENT).node_id
    assert plan.leg_to_receiving_party.node_path[0] == network.node_by_label(INCIDENT).node_id
    assert plan.leg_to_receiving_party.node_path[-1] == network.node_by_label(SHOP_A).node_id
    assert plan.total_cost_minutes == pytest.approx(
        plan.leg_to_incident.total_cost_minutes + plan.leg_to_receiving_party.total_cost_minutes
    )
    assert len(plan.handoffs) == 2
    assert all(h.provider == PROVIDER_GOOGLE for h in plan.handoffs)
    assert "incident scene" in plan.handoffs[0].label.lower() or "leg 1" in plan.handoffs[0].label


def test_dispatch_to_dealer_location(network):
    service = DispatchRoutingService(InMemoryRoutingEngine())
    plan = service.plan(network, make_acceptance("dealer", DEALER), DEPOT, INCIDENT, PROVIDER_APPLE)
    assert plan.acceptance.party_type == "dealer"
    assert plan.leg_to_receiving_party.node_path[-1] == network.node_by_label(DEALER).node_id


def test_dispatch_degenerate_rejected(network):
    service = DispatchRoutingService(InMemoryRoutingEngine())
    with pytest.raises(RoutingError):
        service.plan(network, make_acceptance(location=INCIDENT), INCIDENT, INCIDENT, PROVIDER_GOOGLE)


def test_engine_injection_validated():
    with pytest.raises(RoutingError):
        DispatchRoutingService("not-an-engine")


def test_determinism(network):
    e1, e2 = InMemoryRoutingEngine(), InMemoryRoutingEngine()
    r1 = e1.route(network, 0, 35, k=3)
    r2 = e2.route(network, 0, 35, k=3)
    assert [x.node_path for x in r1] == [x.node_path for x in r2]
    assert [x.total_cost_minutes for x in r1] == [x.total_cost_minutes for x in r2]
