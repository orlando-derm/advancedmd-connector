"""The one log filter, and the logging policy. SPEC 17.3.

There is exactly ONE filter in the process and it is attached to the
root handler, so every logger -- ours, uvicorn's, a copied handler's --
passes through it. Its job:

  * redact any value longer than 200 characters, wherever it appears:
    the message, a %-format argument, or a structured `extra` field.
  * redact any key named password, token, usercontext, result or args,
    whatever its length.

Even at DEBUG, bodies are not logged. That is the point of the length
rule: an AMD XML body, a result dict or an args dict is long, and a
short one still dies on its key name.

Levels (SPEC 17.3): INFO for lifecycle and audit, WARNING for degraded
states / 429s / 1025s, ERROR for internal exceptions with a request_id.
DEBUG is never enabled in production; configure() refuses to hand httpx
anything below WARNING so no HTTP library can log a body.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

__all__ = [
    "MAX_VALUE_CHARS",
    "REDACTED_KEYS",
    "REDACTION",
    "PINNED_WARNING_LOGGERS",
    "RedactingFilter",
    "redact_value",
    "configure",
]

#: SPEC 17.3: anything longer than this is a body, not a log message.
MAX_VALUE_CHARS = 200
#: SPEC 17.3: these keys are redacted regardless of length.
REDACTED_KEYS = frozenset({"password", "token", "usercontext", "result", "args"})
REDACTION = "[redacted]"

#: SPEC 17.3: no HTTP library may log bodies. Pinned, not merely defaulted.
PINNED_WARNING_LOGGERS = ("httpx", "httpcore", "hpack", "urllib3")

_STANDARD_RECORD_ATTRS = frozenset(vars(logging.makeLogRecord({})))


def _is_redacted_key(key: Any) -> bool:
    return str(key).strip().lower() in REDACTED_KEYS


def redact_value(value: Any, key: Any = None) -> Any:
    """Apply the SPEC 17.3 rules to one value.

    A redacted key returns the marker. A long string, or any container
    whose rendering is long, returns the marker. Containers are walked
    so a short dict holding a long body still loses the body.
    """
    if key is not None and _is_redacted_key(key):
        return REDACTION
    if isinstance(value, str):
        return REDACTION if len(value) > MAX_VALUE_CHARS else value
    if isinstance(value, (bool, int, float, type(None))):
        return value
    if isinstance(value, Mapping):
        return {k: redact_value(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        rendered = [redact_value(v) for v in value]
        return type(value)(rendered) if isinstance(value, (list, tuple)) else rendered
    text = str(value)
    return REDACTION if len(text) > MAX_VALUE_CHARS else text


class RedactingFilter(logging.Filter):
    """The single SPEC 17.3 filter. Attach once, to the root handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        # %-format arguments, before they are interpolated.
        if isinstance(record.args, Mapping):
            record.args = {k: redact_value(v, k) for k, v in record.args.items()}
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_value(v) for v in record.args)

        # Structured fields passed through logging's `extra=`.
        for key in list(vars(record)):
            if key in _STANDARD_RECORD_ATTRS:
                continue
            setattr(record, key, redact_value(getattr(record, key), key))

        # The message itself. Interpolate first so a long value cannot
        # survive by hiding behind a placeholder.
        try:
            rendered = record.getMessage()
        except Exception:  # pragma: no cover - a broken format string
            rendered = str(record.msg)
        if len(rendered) > MAX_VALUE_CHARS:
            record.msg = REDACTION
            record.args = ()
        elif rendered != record.msg:
            record.msg = rendered
            record.args = ()
        return True


def configure(
    level: str = "INFO",
    *,
    stream: Any = None,
    extra_pinned: Iterable[str] = (),
) -> RedactingFilter:
    """Install the root handler, the filter, and the WARNING pins.

    Returns the filter so callers can assert it is the only one. Safe to
    call twice: the previous connector handler is replaced, not stacked.
    """
    log_filter = RedactingFilter()
    handler = logging.StreamHandler(stream) if stream is not None else logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(log_filter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))

    for name in (*PINNED_WARNING_LOGGERS, *extra_pinned):
        pinned = logging.getLogger(name)
        pinned.setLevel(logging.WARNING)
        # Pin it: a library that lowers its own level at import time must
        # not be able to start logging bodies.
        pinned.propagate = True
    return log_filter
