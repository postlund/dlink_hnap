"""Base entity for D-Link HNAP integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HNAPDataUpdateCoordinator


class HNAPBaseEntity(CoordinatorEntity[HNAPDataUpdateCoordinator]):
    """Base class for D-Link HNAP entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HNAPDataUpdateCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)

        serial = coordinator.data.get("serial", coordinator.entry.entry_id)
        model = coordinator.data.get("model", "Unknown")
        device_name = coordinator.data.get("device_name", "D-Link Sensor")
        firmware = coordinator.data.get("firmware", "Unknown")
        hw_version = coordinator.data.get("hardware_version")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=device_name,
            manufacturer="D-Link",
            model=model,
            sw_version=firmware,
            hw_version=hw_version if hw_version else None,
        )
