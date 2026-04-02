"""D-Link HNAP integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import HNAPDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up D-Link HNAP from YAML (import to config entry)."""
    hass.data.setdefault(DOMAIN, {})

    # Check for legacy YAML binary_sensor platform config and import it
    if "binary_sensor" in config:
        for platform_config in config["binary_sensor"]:
            if platform_config.get("platform") != DOMAIN:
                continue

            _LOGGER.info(
                "Migrating D-Link HNAP YAML configuration to config entry"
            )
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data={
                        CONF_HOST: platform_config[CONF_HOST],
                        CONF_USERNAME: platform_config.get(CONF_USERNAME, "Admin"),
                        CONF_PASSWORD: platform_config[CONF_PASSWORD],
                    },
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up D-Link HNAP from a config entry."""
    coordinator = HNAPDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a D-Link HNAP config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)