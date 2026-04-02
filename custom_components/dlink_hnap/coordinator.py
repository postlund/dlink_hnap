"""DataUpdateCoordinator for D-Link HNAP integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_MOTION_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .dlink import (
    ACTION_BASE_URL,
    AuthenticationError,
    CannotConnect,
    HNAPClient,
    NanoSOAPClient,
)

_LOGGER = logging.getLogger(__name__)


class HNAPDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching data from a D-Link HNAP device."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry

        # Create API client
        session = async_get_clientsession(hass)
        soap = NanoSOAPClient(
            entry.data[CONF_HOST], ACTION_BASE_URL, session=session
        )
        self.client = HNAPClient(
            soap, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )

        # Capabilities discovered on first update
        self.capabilities: set[str] = set()
        self._capabilities_detected = False

        # Polling interval from options or default
        scan_interval_seconds = entry.options.get(
            "scan_interval", int(DEFAULT_SCAN_INTERVAL.total_seconds())
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval_seconds),
            config_entry=entry,
        )

    @property
    def motion_timeout(self) -> int:
        """Return configured motion timeout in seconds."""
        return self.entry.options.get("motion_timeout", DEFAULT_MOTION_TIMEOUT)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        try:
            # Detect capabilities on first run
            if not self._capabilities_detected:
                self.capabilities = await self.client.detect_capabilities()
                self._capabilities_detected = True
                _LOGGER.info(
                    "Device capabilities: %s", self.capabilities
                )

            data = await self.client.get_all_data(
                capabilities=self.capabilities,
                motion_timeout=self.motion_timeout,
            )

            # Include capabilities in data for entity setup
            data["available_capabilities"] = self.capabilities
            return data

        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except CannotConnect as err:
            raise UpdateFailed(f"Cannot connect to device: {err}") from err
