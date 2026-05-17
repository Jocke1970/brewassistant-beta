"""Next recommended action helper for BrewAssistant."""

from __future__ import annotations

from typing import Any

from .coordinator import BrewAssistantData
from .smart_recommendations import SmartRecommendationData


def build_next_action(
    *,
    data: BrewAssistantData | None,
    smart: SmartRecommendationData | None,
    source_health: dict[str, Any],
) -> dict[str, Any]:
    """Return a compact next recommended action snapshot."""
    if data is None:
        return {
            "action": "Waiting for BrewAssistant data",
            "category": "system",
            "priority": "warning",
            "reason": "Coordinator has no data yet",
            "icon": "mdi:database-clock",
        }

    source_level = str(source_health.get("level", "unknown"))
    source_summary = str(source_health.get("summary", "Source health unknown"))

    if source_level == "problem":
        return {
            "action": "Check source configuration",
            "category": "source_health",
            "priority": "problem",
            "reason": source_summary,
            "icon": "mdi:database-alert",
        }

    if source_level == "warning":
        return {
            "action": "Review source warning",
            "category": "source_health",
            "priority": "warning",
            "reason": source_summary,
            "icon": "mdi:database-search",
        }

    if smart is not None and smart.pill_stale:
        return {
            "action": "Check Pill signal",
            "category": "pill",
            "priority": "problem",
            "reason": smart.pill_status,
            "icon": "mdi:pill-off",
        }

    if not data.ready:
        return {
            "action": "Check runtime inputs",
            "category": "runtime",
            "priority": "problem",
            "reason": "Missing liquid temperature or target temperature",
            "icon": "mdi:database-alert",
        }

    process = data.process_status or "Unknown"
    process_lower = process.lower()
    next_step = data.process_next_step or "Monitor fermentation"

    if "ready for transfer" in process_lower:
        return {
            "action": "Ready for transfer",
            "category": "process",
            "priority": "info",
            "reason": next_step,
            "icon": "mdi:transfer",
        }

    if "ready for cold crash" in process_lower:
        return {
            "action": "Start cold crash",
            "category": "process",
            "priority": "info",
            "reason": next_step,
            "icon": "mdi:snowflake-alert",
        }

    if "dry hop" in process_lower:
        return {
            "action": "Dry hop now",
            "category": "process",
            "priority": "info",
            "reason": next_step,
            "icon": "mdi:leaf",
        }

    if "spunding" in process_lower or "spund" in process_lower:
        return {
            "action": "Check spunding",
            "category": "process",
            "priority": "info",
            "reason": next_step,
            "icon": "mdi:gauge",
        }

    if smart is not None:
        if smart.heat_needed and not smart.heat_permitted:
            return {
                "action": "Heat blocked",
                "category": "smart_fermentation",
                "priority": "warning",
                "reason": smart.block_reason,
                "icon": "mdi:fire-alert",
            }

        if smart.heat_permitted:
            return {
                "action": "Heat pulse recommended",
                "category": "smart_fermentation",
                "priority": "info",
                "reason": smart.heat,
                "icon": "mdi:fire",
            }

        if smart.cooling_recommended and smart.fan_recommended:
            return {
                "action": "Cooling + fan recommended",
                "category": "smart_fermentation",
                "priority": "info",
                "reason": f"{smart.cooling} · {smart.fan}",
                "icon": "mdi:fan-chevron-up",
            }

        if smart.cooling_recommended:
            return {
                "action": "Cooling recommended",
                "category": "smart_fermentation",
                "priority": "info",
                "reason": smart.cooling,
                "icon": "mdi:snowflake",
            }

        if smart.fan_recommended:
            return {
                "action": "Fan assist recommended",
                "category": "smart_fermentation",
                "priority": "info",
                "reason": smart.fan,
                "icon": "mdi:fan",
            }

    if "cold crash" in process_lower:
        return {
            "action": "Maintain cold crash",
            "category": "process",
            "priority": "ok",
            "reason": next_step,
            "icon": "mdi:snowflake-check",
        }

    if "finished" in process_lower or "transferred" in process_lower:
        return {
            "action": "Batch completed",
            "category": "process",
            "priority": "ok",
            "reason": next_step,
            "icon": "mdi:check-circle",
        }

    return {
        "action": "Monitor fermentation",
        "category": "process",
        "priority": "ok",
        "reason": next_step,
        "icon": "mdi:beer-outline",
    }
