"""OpenTelemetry SDK initialisation — traces, metrics, and logs.

Call configure_telemetry() once per process before any instrumentation
libraries activate. Both rs_api/main.py (API) and rs_worker/worker.py use this
module so the configuration is identical across processes.

OTLP endpoint is read from the OTEL_EXPORTER_OTLP_ENDPOINT env var
(compose sets it to http://grafana-alloy:4317). When the variable is absent
(local dev) providers are initialised without exporters — no connection is
attempted and no warnings are emitted; telemetry is simply dropped.
"""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_logger_provider: LoggerProvider | None = None


def configure_telemetry(
    service_name: str,
    service_namespace: str = "rs-recruiting",
    deployment_environment: str | None = None,
) -> None:
    """Initialise TracerProvider, MeterProvider, and LoggerProvider.

    Idempotent — safe to call multiple times; only the first call takes effect.
    """
    global _tracer_provider, _meter_provider, _logger_provider
    if _tracer_provider is not None:
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    env = deployment_environment or os.environ.get("ENVIRONMENT", "dev")

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": service_namespace,
            "deployment.environment": env,
        }
    )

    # Traces
    _tracer_provider = TracerProvider(resource=resource)
    if endpoint:
        _tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )
    trace.set_tracer_provider(_tracer_provider)

    # Metrics — export every 60 s
    _meter_provider = MeterProvider(
        resource=resource,
        metric_readers=(
            [
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=endpoint, insecure=True),
                    export_interval_millis=60_000,
                )
            ]
            if endpoint
            else []
        ),
    )
    metrics.set_meter_provider(_meter_provider)

    # Logs — bridge Python logging → OTel so existing logger.info(...) calls
    # are forwarded to Loki without changing any call sites.
    _logger_provider = LoggerProvider(resource=resource)
    if endpoint:
        _logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True))
        )
    set_logger_provider(_logger_provider)

    # Injects otelTraceID + otelSpanID into every LogRecord for Loki→Tempo correlation.
    # set_logging_format=True is required — with False the record factory is a no-op
    # and otelTraceID/otelSpanID are never added to log records.
    LoggingInstrumentor().instrument(set_logging_format=True)


def shutdown_telemetry() -> None:
    """Flush buffered telemetry and shut down all providers.

    Call during graceful shutdown (lifespan teardown / worker SIGTERM handler).
    """
    if _tracer_provider:
        _tracer_provider.force_flush(timeout_millis=5_000)
        _tracer_provider.shutdown()
    if _meter_provider:
        _meter_provider.shutdown()
    if _logger_provider:
        _logger_provider.force_flush(timeout_millis=5_000)
        _logger_provider.shutdown()


def get_meter(name: str) -> metrics.Meter:
    return metrics.get_meter(name)
