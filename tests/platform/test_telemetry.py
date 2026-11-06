"""
Telemetry facade tests (Slice 6): no-op safety without the SDK, real spans
with it, and env-driven initialization.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import app.telemetry as telemetry
from app.capture_workflow import CaptureWorkflow


def test_noop_tracer_when_sdk_unavailable(monkeypatch):
    monkeypatch.setattr(telemetry, "_API", None)
    monkeypatch.setattr(telemetry, "_INITIALIZED", True)
    tracer = telemetry.get_tracer()
    with tracer.start_as_current_span("anything") as span:
        span.set_attribute("k", "v")
        span.record_exception(ValueError("x"))
        span.set_status(None)
    assert telemetry.initialize() is False


def test_span_helper_is_noop_safe(monkeypatch):
    monkeypatch.setattr(telemetry, "_API", None)
    monkeypatch.setattr(telemetry, "_INITIALIZED", True)
    with telemetry.workflow_span("capture.emit", kind="CONSENT_RECORDED") as span:
        span.set_attribute("c2c.kind", "CONSENT_RECORDED")


def test_initialize_disabled_by_default(monkeypatch):
    monkeypatch.delenv("C2C_OTEL_EXPORTER", raising=False)
    monkeypatch.setattr(telemetry, "_INITIALIZED", False)
    assert telemetry.initialize() is False


def test_workflow_emits_real_spans(monkeypatch):
    """With the SDK present, a capture session produces named, attributed spans."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "_API", __import__("opentelemetry").trace)
    monkeypatch.setattr(telemetry._API, "get_tracer", lambda *a, **k: provider.get_tracer("test"))

    w = CaptureWorkflow("telemetry-session-1", now=lambda: "2026-11-06T18:00:00+00:00")
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    w.record_vehicle("driver-1", "1HGCM82633A004352")

    spans = exporter.get_finished_spans()
    names = [s.name for s in spans]
    assert "capture.emit" in names
    consent_span = [s for s in spans if s.name == "capture.emit" and s.attributes.get("c2c.kind") == "CONSENT_RECORDED"]
    assert consent_span, "consent span must carry its event kind attribute"
    assert any(s.name == "capture.emit" and s.attributes.get("c2c.kind") == "VEHICLE_RECORDED" for s in spans)


def test_console_exporter_initializes(monkeypatch):
    monkeypatch.setenv("C2C_OTEL_EXPORTER", "console")
    monkeypatch.setattr(telemetry, "_INITIALIZED", False)
    assert telemetry.initialize() is True
    # Stop the background span processor before pytest closes captured stdout.
    telemetry._API.get_tracer_provider().shutdown()
