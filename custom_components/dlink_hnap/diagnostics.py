"""Diagnostics support for D-Link HNAP integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import DOMAIN
from .coordinator import HNAPDataUpdateCoordinator

REDACT_KEYS = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HNAPDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "config_entry": async_redact_data(dict(entry.data), REDACT_KEYS),
        "options": dict(entry.options),
        "capabilities": sorted(coordinator.capabilities),
        "coordinator_data": {
            k: v
            for k, v in (coordinator.data or {}).items()
            if k not in ("serial",)  # Redact serial from diagnostics
        },
        "device_actions": sorted(coordinator.client.actions or []),
    }
