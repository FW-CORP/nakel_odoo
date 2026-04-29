import logging
import os

_logger = logging.getLogger(__name__)


def _setup_otel():
    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
    except ImportError as e:
        _logger.warning("OpenTelemetry packages not available, skipping instrumentation: %s", e)
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    environment = os.environ.get("ODOO_ENV", "production")

    resource = Resource.create({
        "service.name": "odoo-nakel",
        "service.version": "18",
        "deployment.environment": environment,
    })

    # --- Traces ---
    tracer_provider = TracerProvider(resource=resource)

    if endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )

    trace.set_tracer_provider(tracer_provider)

    # --- Metrics ---
    if endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint, insecure=True),
            export_interval_millis=30_000,
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    else:
        meter_provider = MeterProvider(resource=resource)

    metrics.set_meter_provider(meter_provider)

    # --- Instrumentors ---
    Psycopg2Instrumentor().instrument(enable_commenter=True, commenter_options={})
    _patch_execute_values()
    LoggingInstrumentor().instrument(set_logging_format=True)
    RequestsInstrumentor().instrument()
    URLLib3Instrumentor().instrument()

    _logger.info("OpenTelemetry initialized — endpoint: %s, env: %s", endpoint, environment)


def _patch_execute_values():
    """psycopg2.extras.execute_values builds its query as bytes and calls cur.execute(bytes).
    The OTel sqlcommenter doesn't handle bytes and converts them to their Python repr (b"..."),
    which PostgreSQL rejects with a syntax error. Wrap execute_values to decode bytes before
    they reach OTel."""
    import psycopg2.extras as _pg_extras

    _orig = _pg_extras.execute_values

    def _patched(cur, sql, argslist, template=None, page_size=100, fetch=False):
        _orig_execute = cur.execute

        def _bytes_safe_execute(operation, *args, **kwargs):
            if isinstance(operation, (bytes, bytearray)):
                operation = operation.decode('utf-8')
            return _orig_execute(operation, *args, **kwargs)

        cur.execute = _bytes_safe_execute
        try:
            return _orig(cur, sql, argslist, template=template, page_size=page_size, fetch=fetch)
        finally:
            cur.execute = _orig_execute

    _pg_extras.execute_values = _patched


_setup_otel()

from . import models
