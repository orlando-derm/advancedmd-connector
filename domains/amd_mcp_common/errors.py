"""Typed tool-error envelopes (lifted from legacy amd-mcp-server) +
the deterministic AMD error translation layer (D4.1).

Identical to ``amd_mcp.errors`` for back-compat; lives here so per-
domain servers can import from a stable common location without
depending on the legacy package.

D4.1 added `translate_amd_error()` to convert raw AMD fault XML,
HTTP non-200 responses, and `client.call(...)` exceptions into a
structured `{error, details, user_safe_message}` envelope that Adam
(the chatbot) can read without ever seeing raw XML.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


class RateLimitError(BaseModel):
    error: Literal["rate_limit"] = "rate_limit"
    tier: int
    retry_after_s: float
    peak: bool
    limit_per_minute: int

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class AuthError(BaseModel):
    error: Literal["auth"] = "auth"
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class AmdFaultError(BaseModel):
    error: Literal["amd_fault"] = "amd_fault"
    code: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class WriteAttemptError(BaseModel):
    """Raised by the wrap-tool layer when a handler tries an AMD action
    not in its allowlist. The envelope name has historical meaning:
    write tools are the common cause."""

    error: Literal["write_blocked"] = "write_blocked"
    attempted_action: str
    note: str = (
        "Write actions are blocked at the wrap_tool layer. The flag "
        "`WRITE_TOOLS_ENABLED=False` filters write handlers from "
        "`list_tools()`. Per-domain promotion to True requires a separate "
        "decision file + Aaron approval."
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ValidationError(BaseModel):
    error: Literal["bad_input"] = "bad_input"
    details: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class UnknownToolError(BaseModel):
    """Returned by ``call_tool`` when the dispatch table has no entry
    for the named tool. This includes write-tool names when
    WRITE_TOOLS_ENABLED is False — the filter happens in both
    ``list_tools`` and the dispatch table."""

    error: Literal["unknown_tool"] = "unknown_tool"
    tool: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def to_envelope(exc: BaseException) -> dict[str, Any]:
    name = type(exc).__name__
    msg = str(exc)
    if name == "AuthError":
        return AuthError(reason=msg).to_dict()
    if name == "APIError":
        code = getattr(exc, "code", None)
        desc = getattr(exc, "description", None) or msg or None
        return AmdFaultError(
            code=str(code) if code is not None else None,
            description=desc,
        ).to_dict()
    return AmdFaultError(
        code=None,
        description=f"{name}: {msg}" if msg else name,
    ).to_dict()


# ---------------------------------------------------------------------------
# D4 — AMD error translation layer
# ---------------------------------------------------------------------------


# Stable error codes the chatbot loop can branch on. NEVER expose raw
# AMD XML, credentials, or PHI through any of these fields.
_AMD_ERROR_CODES = frozenset({
    "amd_auth_expired",
    "amd_rate_limited",
    "amd_unknown_action",
    "amd_invalid_arg",
    "amd_no_results",
    "amd_upstream_error",
})


# User-safe one-liner per code. Front-desk-staff-readable; no jargon.
_DEFAULT_USER_SAFE_MESSAGES = {
    "amd_auth_expired": (
        "The connection to AdvancedMD needs to refresh. Try again in a moment."
    ),
    "amd_rate_limited": (
        "AdvancedMD is rate-limiting requests right now. Try again shortly."
    ),
    "amd_unknown_action": (
        "That request isn't supported by AdvancedMD. Try a different lookup."
    ),
    "amd_invalid_arg": (
        "AdvancedMD rejected the request — the value provided wasn't valid."
    ),
    "amd_no_results": (
        "AdvancedMD didn't return any results for that lookup."
    ),
    "amd_upstream_error": (
        "AdvancedMD didn't respond as expected. Try again in a moment."
    ),
}


# Tag stripper for safe excerpts. Strips all `<...>` (XML) before
# truncating to keep `details.message` jargon-free.
_XML_TAG_RE = re.compile(r"<[^>]+>")


def _safe_excerpt(text: str, *, max_len: int = 200) -> str:
    """Strip XML tags + trim whitespace + truncate, for `details.message`.

    Never includes the original XML form — only the human-language
    text content. Truncates at `max_len` chars to keep envelopes
    bounded.
    """
    if not text:
        return ""
    no_tags = _XML_TAG_RE.sub(" ", str(text))
    collapsed = " ".join(no_tags.split())
    if len(collapsed) > max_len:
        return collapsed[: max_len - 1] + "…"
    return collapsed


def _classify_message(s: str) -> str | None:
    """Heuristic AMD-fault-string → error-code mapping.

    AMD's fault shapes vary across actions; this maps common
    substrings to a canonical code. Returns None when no rule fires.
    """
    if not s:
        return None
    low = s.lower()
    # Auth / session expired.
    if "expired" in low and ("session" in low or "context" in low or "auth" in low):
        return "amd_auth_expired"
    if "invalid usercontext" in low or "user context" in low:
        return "amd_auth_expired"
    if "not logged in" in low or "login required" in low:
        return "amd_auth_expired"
    # Rate limit / throttle.
    if "rate limit" in low or "throttl" in low or "too many request" in low:
        return "amd_rate_limited"
    # Unknown action.
    if "unknown action" in low or "action not supported" in low \
            or "invalid action" in low:
        return "amd_unknown_action"
    # Invalid argument.
    if "invalid" in low and ("arg" in low or "parameter" in low
                              or "value" in low or "date" in low):
        return "amd_invalid_arg"
    if "missing required" in low:
        return "amd_invalid_arg"
    # No-results.
    if "no results" in low or "no matching" in low or "not found" in low:
        return "amd_no_results"
    return None


def _looks_like_amd_fault(raw_dict: Any) -> tuple[bool, str | None, str | None]:
    """Inspect a `raw_to_dict` envelope for an AMD in-band fault.

    Returns `(is_fault, code, description)`. `is_fault=True` when
    a `<usercontext><results><result success="0">` marker (or any
    equivalent AMD failure shape) is present. The returned code +
    description are AMD's own; the caller maps to a canonical code.
    """
    if not isinstance(raw_dict, dict):
        return False, None, None

    is_fault = False
    code: str | None = None
    description: str | None = None

    def _walk(node: Any) -> None:
        nonlocal is_fault, code, description
        if not isinstance(node, dict):
            return
        tag = node.get("_tag")
        attrs = node.get("_attrs") or {}
        # Pattern 1: <result success="0" ...>
        if tag == "result" and str(attrs.get("success", "")).strip() == "0":
            is_fault = True
            code = code or attrs.get("errorcode") or attrs.get("code")
            description = description or attrs.get("errordesc") \
                or attrs.get("description") or node.get("_text")
        # Pattern 2: <fault ...>
        if tag == "fault" or tag == "Fault":
            is_fault = True
            description = description or node.get("_text")
        # Pattern 3: errorcode attr anywhere with non-empty value.
        ec = attrs.get("errorcode") or attrs.get("error_code")
        if ec and str(ec).strip() not in ("", "0"):
            is_fault = True
            code = code or str(ec)
            description = description \
                or attrs.get("errordesc") or attrs.get("description")
        for child in node.get("_children") or []:
            _walk(child)

    _walk(raw_dict)
    return is_fault, code, description


def translate_amd_error(payload: Any) -> dict[str, Any]:
    """Translate a raw AMD failure into a structured envelope.

    Accepts:
    - A `raw_to_dict` envelope from a handler that detected an
      in-band AMD fault. The translator walks the envelope and
      returns the right code.
    - An `Exception` raised by `client.call(...)` (auth, network,
      AMD parse error, etc.).
    - A plain string (treated as the human description).

    Returns a dict of shape:
        {"error": "<code>",
         "details": {...},
         "user_safe_message": "<one line>"}

    NEVER contains raw XML, credentials, or PHI in the
    `user_safe_message`. The `details` may include a
    sanitized `message` excerpt (tags stripped, truncated).
    """
    # Case 1: exception input.
    if isinstance(payload, BaseException):
        name = type(payload).__name__
        msg = str(payload)
        code = "amd_upstream_error"
        if name in ("AuthError", "Unauthorized"):
            code = "amd_auth_expired"
        else:
            classified = _classify_message(msg)
            if classified is not None:
                code = classified
            elif name == "APIError":
                # Legacy AMD client APIError -> upstream by default.
                code = "amd_upstream_error"
        details: dict[str, Any] = {
            "exception_type": name,
            "message": _safe_excerpt(msg),
        }
        amd_code = getattr(payload, "code", None)
        if amd_code is not None:
            details["amd_code"] = str(amd_code)
        return {
            "error": code,
            "details": details,
            "user_safe_message": _DEFAULT_USER_SAFE_MESSAGES[code],
        }

    # Case 2: raw_to_dict envelope.
    if isinstance(payload, dict):
        is_fault, amd_code, amd_desc = _looks_like_amd_fault(payload)
        if is_fault:
            classified = _classify_message(amd_desc or "")
            code = classified or "amd_upstream_error"
            details = {"message": _safe_excerpt(amd_desc or "")}
            if amd_code is not None:
                details["amd_code"] = str(amd_code)
            return {
                "error": code,
                "details": details,
                "user_safe_message": _DEFAULT_USER_SAFE_MESSAGES[code],
            }
        # Not a fault — return a "looks ok" passthrough marker so the
        # caller can branch.
        return {
            "error": "ok",
            "details": {},
            "user_safe_message": "",
        }

    # Case 3: plain string.
    if isinstance(payload, str):
        classified = _classify_message(payload) or "amd_upstream_error"
        return {
            "error": classified,
            "details": {"message": _safe_excerpt(payload)},
            "user_safe_message": _DEFAULT_USER_SAFE_MESSAGES[classified],
        }

    # Anything else — unknown payload shape.
    return {
        "error": "amd_upstream_error",
        "details": {"message": _safe_excerpt(repr(payload))},
        "user_safe_message": _DEFAULT_USER_SAFE_MESSAGES["amd_upstream_error"],
    }


def safe_amd_call(client, *, action: str, raw_to_dict_fn, **kwargs):
    """Call `client.call(...)` and inspect the result for AMD faults.

    Returns a 2-tuple `(raw_dict_or_None, error_envelope_or_None)`:
    - On success: `(raw_dict, None)` — handler proceeds to enrichment.
    - On transport/exception: `(None, error_envelope)` — handler
      returns the envelope directly.
    - On in-band AMD fault: `(raw_dict, error_envelope)` — both are
      set so handlers can choose to emit the envelope OR include
      `raw` alongside (the canonical pattern is: return the envelope
      with `raw` attached).

    `raw_to_dict_fn` is passed in by the caller because each domain's
    `_common.raw_to_dict` is locally defined (mirroring the legacy
    helper); the translator can't import any one domain's version.
    """
    try:
        raw = client.call(action=action, **kwargs)
    except BaseException as exc:  # noqa: BLE001 — surface the envelope
        return None, translate_amd_error(exc)
    raw_dict = raw_to_dict_fn(raw)
    envelope = translate_amd_error(raw_dict)
    if envelope.get("error") and envelope["error"] != "ok":
        return raw_dict, envelope
    return raw_dict, None
