import os

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

    FastAPIInstrumentor.instrument_app(app)


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
