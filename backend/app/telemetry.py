"""
OpenTelemetry instrumentation helper.
Provides graceful no-op fallback if opentelemetry is not installed.
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace

    _tracer = trace.get_tracer("vigil")

    @contextlib.contextmanager
    def create_span(name: str, attributes: Dict[str, Any] = None):
        with _tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            yield span

except ImportError:
    class _NoOpSpan:
        def set_attribute(self, key: str, value: Any):
            pass

    @contextlib.contextmanager
    def create_span(name: str, attributes: Dict[str, Any] = None):
        yield _NoOpSpan()
