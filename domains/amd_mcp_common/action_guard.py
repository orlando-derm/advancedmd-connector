"""AMDActionGuard (lifted from legacy amd-mcp-server tools/_common.py).

Proxies an AMD client and enforces a per-handler allowlist on every
outbound call. The structural enforcement of invariant I1 (read-only
default + per-tool guard).

Allowlist schema (unchanged from legacy):

    permitted_actions = (
        "getdatevisits",                          # plain string entry
        ("lookup", {"class_": {"carrier"}}),      # action + kwarg filter
    )

A kwarg filter ``{kwarg_name: {allowed_values}}`` enforces that when
the named action is called, the listed kwarg's value MUST be one of
the allowed values.

``wrap_tool`` moved to ``base_server.py``; this module owns the guard
class and the ContextVar that connects handler-side ``_get_client()``
helpers to the active guard.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Mapping

_LOG = logging.getLogger("amd_mcp_common.action_guard")


AllowlistEntry = Any  # str | tuple[str, Mapping[str, set]]


class AmdActionDeniedError(Exception):
    """Raised when a handler attempts an AMD action that is not in its
    per-handler allowlist. Mapped to a ``WriteAttemptError`` envelope by
    ``wrap_tool``.
    """

    def __init__(self, action: str, reason: str = "") -> None:
        self.attempted_action = action
        self.reason = reason
        super().__init__(
            f"AMD action {action!r} denied: {reason}" if reason
            else f"AMD action {action!r} denied"
        )


# ContextVar threading the active guard factory to handler-side
# ``_get_client()`` helpers.
_current_amd_proxy: ContextVar[Any | None] = ContextVar(
    "amd_mcp_common_current_amd_proxy", default=None
)


def _normalize_allowlist(
    entries: tuple[AllowlistEntry, ...],
) -> dict[str, list[Mapping[str, set]]]:
    out: dict[str, list[Mapping[str, set]]] = {}
    for entry in entries:
        if isinstance(entry, str):
            out.setdefault(entry, []).append({})  # no filter
        elif isinstance(entry, tuple) and len(entry) == 2:
            action, kwarg_filter = entry
            if not isinstance(action, str) or not isinstance(kwarg_filter, Mapping):
                raise TypeError(
                    f"allowlist entry tuple must be (str, Mapping); got {entry!r}"
                )
            normalized = {k: set(v) for k, v in kwarg_filter.items()}
            out.setdefault(action, []).append(normalized)
        else:
            raise TypeError(
                f"allowlist entries must be str or (str, dict); got {entry!r}"
            )
    return out


class AMDActionGuard:
    """Proxy around an AMD client enforcing a per-handler allowlist."""

    _HELPER_ACTIONS: dict[str, str] = {
        "get_visits_for_date": "getdatevisits",
        "get_appointments_via_reminders": "getreminderappts",
        "get_patient_bundle": "getdemographic",
    }

    def __init__(
        self,
        real_client: Any,
        allowed_actions: tuple[AllowlistEntry, ...],
    ) -> None:
        self._client = real_client
        self._allowed = _normalize_allowlist(allowed_actions)

    def _check(self, action: str, kwargs: Mapping[str, Any]) -> None:
        if action not in self._allowed:
            raise AmdActionDeniedError(
                action,
                reason=f"action not in handler allowlist {sorted(self._allowed)!r}",
            )
        filters = self._allowed[action]
        for f in filters:
            if not f:
                return
            ok = True
            for kwarg_name, allowed_values in f.items():
                actual = kwargs.get(kwarg_name)
                if actual not in allowed_values:
                    ok = False
                    break
            if ok:
                return
        raise AmdActionDeniedError(
            action,
            reason=(
                f"kwargs {dict(kwargs)!r} do not match any allowed filter "
                f"for action={action!r}"
            ),
        )

    def call(self, action: str, *args: Any, **kwargs: Any) -> Any:
        if args:
            if "class_" not in kwargs and len(args) >= 1:
                kwargs = {"class_": args[0], **kwargs}
                args = args[1:]
        self._check(action, kwargs)
        if "class_" in kwargs and hasattr(self._client, "call"):
            try:
                return self._client.call(action, **kwargs)
            except TypeError:
                class_ = kwargs.pop("class_")
                return self._client.call(action, class_, **kwargs)
        return self._client.call(action, **kwargs)

    def login(self, *args: Any, **kwargs: Any) -> Any:
        return self._client.login(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name in self._HELPER_ACTIONS:
            implied_action = self._HELPER_ACTIONS[name]

            def _gated_helper(*args: Any, **kwargs: Any) -> Any:
                self._check(implied_action, kwargs)
                return getattr(self._client, name)(*args, **kwargs)

            return _gated_helper
        raise AmdActionDeniedError(
            action=name,
            reason=(
                f"attribute {name!r} is not a permitted entry point; "
                "handlers may only use call/login/get_visits_for_date/"
                "get_appointments_via_reminders/get_patient_bundle"
            ),
        )


class GuardFactory:
    """Stored in the ContextVar so handler-side ``_get_client()`` can ask:

    "is there an active wrap_tool guard? If so, give me a guarded view
    of the raw client; otherwise, give me the raw client."
    """

    def __init__(self, allowed_actions: tuple[AllowlistEntry, ...]) -> None:
        self._allowed_actions = allowed_actions

    def wrap(self, raw_client: Any) -> AMDActionGuard:
        return AMDActionGuard(raw_client, self._allowed_actions)


def maybe_guarded(raw_client: Any) -> Any:
    """Return a guard-wrapped client when a wrap_tool is active, else raw."""
    gf = _current_amd_proxy.get()
    if gf is None:
        return raw_client
    return gf.wrap(raw_client)
