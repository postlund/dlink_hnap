"""Binary sensor platform for D-Link HNAP integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CAP_MOTION, CAP_WATER, DOMAIN
from .coordinator import HNAPDataUpdateCoordinator
from .entity import HNAPBaseEntity


@dataclass(frozen=True, kw_only=True)
class HNAPBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an HNAP binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    required_capability: str


BINARY_SENSOR_DESCRIPTIONS: tuple[HNAPBinarySensorEntityDescription, ...] = (
    HNAPBinarySensorEntityDescription(
        key="water",
        translation_key="water",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda data: data.get("water_detected"),
        required_capability=CAP_WATER,
    ),
    HNAPBinarySensorEntityDescription(
        key="motion",
        translation_key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda data: data.get("motion_detected"),
        required_capability=CAP_MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up D-Link HNAP binary sensors from a config entry."""
    coordinator: HNAPDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        HNAPBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.required_capability in coordinator.capabilities
    ]

    async_add_entities(entities)


class HNAPBinarySensor(HNAPBaseEntity, BinarySensorEntity):
    """Representation of a D-Link HNAP binary sensor."""

    entity_description: HNAPBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HNAPDataUpdateCoordinator,
        description: HNAPBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        serial = coordinator.data.get("serial", coordinator.entry.entry_id)
        self._attr_unique_id = f"{serial}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
