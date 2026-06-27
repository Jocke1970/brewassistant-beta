"""BrewZilla target trust guard.

RAPT Cloud can echo an older target for one or more polls after BA has just sent
a new BrewZilla target. Without a short trust window BA keeps re-sending the same
target because the HA number entity temporarily appears to rewind.
"""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as base

_BASE_BUILD = None
_BASE_APPLY = None
_INSTALLED = False
STORE = "brewzilla_target_trust_guard"
TRUST_WINDOW_SECONDS = 90


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _store(hass) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(STORE, {})


def _age_seconds(raw: Any) -> int | None:
    if not raw:
        return None
    parsed = dt_util.parse_datetime(str(raw))
    if parsed is None:
        return None
    return max(0, int((dt_util.utcnow() - dt_util.as_utc(parsed)).total_seconds()))


def _apply_target_trust(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    out = dict(snapshot)
    requested = _num(out.get("requested_target"))
    st = _store(hass)
    trusted_target = _num(st.get("target"))
    trusted_age = _age_seconds(st.get("updated_at"))
    active = bool(
        trusted_target is not None
        and requested is not None
        and trusted_age is not None
        and trusted_age <= TRUST_WINDOW_SECONDS
        and abs(trusted_target - requested) <= base.TARGET_SYNC_TOLERANCE
    )

    out.update({
        "target_trust_guard_active": active,
        "target_trust_guard_seconds": TRUST_WINDOW_SECONDS,
        "target_trust_guard_age_seconds": trusted_age,
        "target_trust_guard_target": trusted_target,
        "target_trust_guard_rcl_target": out.get("applied_target"),
    })

    if not active or requested is None or trusted_target is None:
        return out

    rcl_target = _num(out.get("applied_target"))
    rcl_age = _num(out.get("rapt_brewzilla_target_age_seconds"))
    rcl_stale_or_rewound = bool(
        rcl_target is None
        or abs(rcl_target - requested) > base.TARGET_SYNC_TOLERANCE
        or (rcl_age is not None and rcl_age > TRUST_WINDOW_SECONDS)
    )
    if not rcl_stale_or_rewound:
        return out

    out["applied_target"] = trusted_target
    out["target_delta"] = 0.0
    out["target_sync_needed"] = False
    out["target_trust_guard_suppressed_sync"] = True
    out["control_reason"] = "BA target trust active; stale RCL target echo suppressed. " + str(out.get("control_reason") or "")
    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _apply_target_trust(hass, _BASE_BUILD(hass))


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_APPLY is not None
    result = await _BASE_APPLY(hass)
    if result.get("target_changed") and result.get("applied_target_value") is not None:
        _store(hass).update({
            "target": float(result["applied_target_value"]),
            "updated_at": dt_util.utcnow().isoformat(),
            "source": "brewzilla_apply",
            "result": result.get("apply_result"),
        })
    return result


def install_target_trust_guard() -> None:
    global _BASE_BUILD, _BASE_APPLY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    _BASE_APPLY = base.async_apply_brewzilla_target_if_allowed
    base.build_orchestration_snapshot = build_orchestration_snapshot
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
