"""OpenTelemetry facade (Slice 6; CTO brief Tier 1 #5).

Zero-cost observability scaffolding: when the opentelemetry API/SDK are
installed and an exporter is configured, workflow operations emit real
traces; when absent, every call is a no-op with the identical interface, so
core logic never gains a hard dependency and the frozen contracts stay
dependency-free.

Conventions:
- Service name: C2C_TELEMETRY_SERVICE_NAME (default "claim2car-connect").
- Exporter: C2C_OTEL_EXPORTER = "none" (default) | "console" | "otlp".
- Sampling: C2C_OTEL_SAMPLE_RATIO (default "1.0"; "0" disables).
- Span names follow the workflow kind (e.g. "capture.session_created").
"""
from __future__ import annotations

import os
from contextlib import contextmanager

_API = None
try:  # optional dependency: no-op when absent
    from opentelemetry import trace as _otel_trace

    _API = _otel_trace
except Exception:  # pragma: no cover - exercised when OTel is not installed
    _API = None

_INITIALIZED = False


class _NoOpSpan:
    def set_attribute(self, key, value):  # noqa: D401 - interface parity
        return None

    def record_exception(self, exception):
        return None

    def set_status(self, status):
        return None


class _NoOpTracer:
    @contextmanager
    def start_as_current_span(self, name, **kwargs):
        yield _NoOpSpan()


_NOOP_TRACER = _NoOpTracer()


def initialize() -> bool:
    """Configure the global OTel pipeline once. Returns True if tracing is live."""
    global _INITIALIZED
    if _INITIALIZED:
        return _API is not None
    _INITIALIZED = True
    if _API is None:
        return False
    exporter = os.environ.get("C2C_OTEL_EXPORTER", "none").strip().lower()
    if exporter in ("", "none"):
        return False
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        ratio_raw = os.environ.get("C2C_OTEL_SAMPLE_RATIO", "1.0")
        try:
            ratio = min(1.0, max(0.0, float(ratio_raw)))
        except ValueError:
            ratio = 1.0
        service = os.environ.get("C2C_TELEMETRY_SERVICE_NAME", "claim2car-connect")
        provider = TracerProvider(
            resource=Resource.create({"service.name": service}),
            sampler=TraceIdRatioBased(ratio),
        )
        if exporter == "console":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        elif exporter == "otlp":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # optional

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        else:
            return False
        _API.set_tracer_provider(provider)
        return True
    except Exception:  # pragma: no cover - misconfiguration must never break the app
        return False


def get_tracer():
    """Return a tracer with start_as_current_span(name) — real or no-op."""
    if _API is None:
        return _NOOP_TRACER
    return _API.get_tracer("claim2car.connect/app")


def span_name(*parts):
    """Stable dotted span naming: span_name('capture', 'consent') -> 'capture.consent'."""
    return ".".join(str(p) for p in parts if p)


@contextmanager
def workflow_span(name: str, **attributes):
    """Context manager wrapping a workflow operation in a span (no-op safe)."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            try:
                current.set_attribute(f"c2c.{key}", value)
            except Exception:  # pragma: no cover - attribute failures never break flow
                pass
        yield current
