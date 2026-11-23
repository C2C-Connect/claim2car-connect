"""Regression coverage for fail-closed integrity API inputs and diagnostics."""
from app.api.triage import AdjudicateRequest, adjudicate, triage_health


def test_health_names_the_integrity_contract_implemented_by_s_i():
    assert "s_i_weighted_sum_strict_chain" in triage_health()["modules"]


def test_adjudication_api_reports_incomplete_chain_collapse():
    response = adjudicate(AdjudicateRequest(
        session_id="api-integrity-incomplete-chain",
        gps_accuracy_m=5,
        chain_coverage=0.99,
        chain_uniqueness=1.0,
        meta_completeness=1.0,
    ))
    integrity = response["integrity"]
    assert integrity["c_chain"] == 0.0
    assert integrity["c_hash"] == 0.0
    assert integrity["s_i"] == 0.0
    assert integrity["all_or_nothing_collapse"] is True
    assert integrity["chain_failure_reason"] == "CHAIN_COVERAGE_INCOMPLETE"
    assert abs(integrity["c_chain_geometric"] - (0.99 ** 0.5)) < 1e-4


def test_api_accepts_and_applies_tamper_and_spoof_signals():
    for field, reason in (
        ("hash_tamper_suspected", "HASH_TAMPER_SUSPECTED"),
        ("gps_spoof_suspected", "HASH_TAMPER_SUSPECTED"),
    ):
        body = AdjudicateRequest(session_id=f"api-integrity-{field}", **{field: True})
        response = adjudicate(body)
        integrity = response["integrity"]
        assert integrity["s_i"] == 0.0
        assert integrity["all_or_nothing_collapse"] is True
        assert integrity["chain_failure_reason"] == reason
