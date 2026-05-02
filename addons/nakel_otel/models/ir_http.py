import logging
from odoo import models
from opentelemetry import trace
from opentelemetry.semconv.trace import SpanAttributes

_logger = logging.getLogger(__name__)
_tracer = trace.get_tracer("odoo.http")


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        request = cls._get_request()
        http_method = getattr(request, 'httprequest', None)

        span_name = getattr(endpoint, '__name__', 'unknown')
        route = getattr(getattr(endpoint, 'routing', None), 'get', lambda k, v: v)('routes', [span_name])
        if isinstance(route, (list, tuple)) and route:
            span_name = route[0]

        with _tracer.start_as_current_span(
            f"odoo.http {span_name}",
            kind=trace.SpanKind.SERVER,
        ) as span:
            if http_method:
                span.set_attribute(SpanAttributes.HTTP_METHOD, http_method.method)
                span.set_attribute(SpanAttributes.HTTP_URL, http_method.url)
                span.set_attribute(SpanAttributes.HTTP_ROUTE, span_name)

            try:
                response = super()._dispatch(endpoint)
                if hasattr(response, 'status_code'):
                    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(trace.StatusCode.ERROR, str(exc))
                raise

    @classmethod
    def _get_request(cls):
        try:
            from odoo.http import request
            return request
        except Exception:
            return None
