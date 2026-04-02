"""Sensor platform for D-Link HNAP integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CAP_TEMPERATURE, DOMAIN
from .coordinator import HNAPDataUpdateCoordinator
from .entity import HNAPBaseEntity


@dataclass(frozen=True, kw_only=True)
class HNAPSensorEntityDescription(SensorEntityDescription):
    """Describes an HNAP sensor entity."""

    value_fn: Callable[[dict[str, Any]], float | str | None]
    required_capability: str | None = None


SENSOR_DESCRIPTIONS: tuple[HNAPSensorEntityDescription, ...] = (
    HNAPSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.get("temperature"),
        required_capability=CAP_TEMPERATURE,
    ),
    HNAPSensorEntityDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:package-variant",
        value_fn=lambda data: data.get("firmware"),
        required_capability=None,  # Always available
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up D-Link HNAP sensors from a config entry."""
    coordinator: HNAPDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        HNAPSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.required_capability is None
        or description.required_capability in coordinator.capabilities
    ]

    async_add_entities(entities)


class HNAPSensor(HNAPBaseEntity, SensorEntity):
    """Representation of a D-Link HNAP sensor."""

    entity_description: HNAPSensorEntityDescription

    def __init__(
        self,
        coordinator: HNAPDataUpdateCoordinator,
        description: HNAPSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        serial = coordinator.data.get("serial", coordinator.entry.entry_id)
        self._attr_unique_id = f"{serial}_{description.key}"

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
