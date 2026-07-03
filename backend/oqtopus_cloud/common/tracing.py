import os
import random

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_provider: TracerProvider | None = None


def setup_tracing(app: FastAPI, service_name: str) -> None:
    """Wire OpenTelemetry into the FastAPI app when OTEL_ENABLED=true.

    The OTLP exporter reads OTEL_EXPORTER_OTLP_TRACES_ENDPOINT /
    OTEL_EXPORTER_OTLP_ENDPOINT from the environment on its own, so no
    explicit endpoint is passed in.

    ``LoggingInstrumentor(set_logging_format=True)`` is required for
    aws-lambda-powertools' structured logger to surface ``otelTraceID`` /
    ``otelSpanID`` in its JSON output — without it the LogRecord attributes
    are injected but the formatter does not emit them. The trade-off is one
    extra plain-text log line per record from the OTel default formatter;
    that duplication is acceptable for the log<>trace correlation benefit.
    """
    global _provider
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return

    if _provider is None:
        _provider = TracerProvider(
            resource=Resource.create({SERVICE_NAME: service_name})
        )
        _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(_provider)
        SQLAlchemyInstrumentor().instrument()
        LoggingInstrumentor().instrument(set_logging_format=True)
        _register_snapstart_restore_hook()

    FastAPIInstrumentor.instrument_app(app)


def _reseed_random_after_snapstart() -> None:
    # SnapStart takes one memory snapshot at the end of Init and restores it
    # into every execution environment. The ``random`` module's global state is
    # frozen into that snapshot, so without re-seeding each restored environment
    # generates the *same* sequence of values — including OTel trace/span IDs,
    # because ``RandomIdGenerator`` draws them from ``random.getrandbits``.
    # Identical sequences make unrelated invocations collide on a single trace
    # ID (the symptom: distinct requests merged under one multi-hour trace).
    #
    # ``random.seed()`` (no argument) reseeds from OS entropy, giving each
    # restored environment an independent stream. Seeding the module global is
    # enough: every already-created ``RandomIdGenerator`` reads from it.
    random.seed()


def _register_snapstart_restore_hook() -> None:
    # ``snapshot_restore_py`` ships with the AWS Lambda managed Python runtime.
    # It is absent locally and in tests — where there is no snapshot to restore
    # — so a missing import is a no-op.
    try:
        from snapshot_restore_py import register_after_restore  # type: ignore[import-not-found]
    except ImportError:
        return
    register_after_restore(_reseed_random_after_snapstart)


def force_flush(timeout_millis: int | None = None) -> None:
    # BatchSpanProcessor runs on a daemon thread that the Lambda runtime
    # freezes between invocations, so spans never reach the exporter unless
    # flushed synchronously before returning. No-op when OTel is disabled.
    #
    # Default 500ms caps the worst-case user-visible delay when the collector
    # is slow or unreachable. Override with OTEL_FORCE_FLUSH_TIMEOUT_MS in
    # environments that prefer to wait longer.
    if _provider is None:
        return
    if timeout_millis is None:
        timeout_millis = int(os.getenv("OTEL_FORCE_FLUSH_TIMEOUT_MS", "500"))
    _provider.force_flush(timeout_millis)
