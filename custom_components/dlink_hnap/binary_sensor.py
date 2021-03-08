"""Support for D-Link motion sensors."""
import logging
from datetime import timedelta, datetime

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    PLATFORM_SCHEMA,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_MOISTURE,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_HOST,
    CONF_TIMEOUT,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .dlink import (
    HNAPClient,
    MotionSensor,
    WaterSensor,
    NanoSOAPClient,
    ACTION_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dlink_hnap"

DEFAULT_NAME = "D-Link Motion Sensor"
DEFAULT_USERNAME = "Admin"
DEFAULT_TIMEOUT = 35

SCAN_INTERVAL = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_TYPE): vol.In(["motion", "water"]),
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the D-Link motion sensor."""
    soap = NanoSOAPClient(
        config.get(CONF_HOST), ACTION_BASE_URL, async_get_clientsession(hass),
    )

    client = HNAPClient(soap, config.get(CONF_USERNAME), config.get(CONF_PASSWORD))

    if config.get(CONF_TYPE) == "motion":
        sensor = DlinkMotionSensor(
            config.get(CONF_NAME), config.get(CONF_TIMEOUT), MotionSensor(client)
        )
    else:
        sensor = DlinkWaterSensor(config.get(CONF_NAME), WaterSensor(client))

    async_add_devices([sensor], update_before_add=True)


class DlinkBinarySensor(BinarySensorEntity):
    """Representation of a D-Link binary sensor."""

    def __init__(self, name, sensor, device_class):
        """Initialize the D-Link motion binary sensor."""
        self._name = name
        self._sensor = sensor
        self._device_class = device_class
        self._on = False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._on

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def unique_id(self):
        """Return unique ID for sensor."""
        return self._sensor.mac

    @property
    def device_info(self):
        """Return a device description for device registry."""
        description = self._sensor.model_description
        model = self._sensor.model
        hardware = self._sensor.hardware
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": self._sensor.vendor,
            "model": f"{description} {model} ({hardware})",
            "sw_version": self._sensor.firmware,
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._sensor.mac)},
        }


class DlinkMotionSensor(DlinkBinarySensor):
    """Representation of a D-Link motion sensor."""

    def __init__(self, name, timeout, sensor):
        """Initialize the D-Link motion binary sensor."""
        super().__init__(name, sensor, DEVICE_CLASS_MOTION)
        self._timeout = timeout

    async def async_update(self):
        """Get the latest data and updates the states."""
        try:
            last_trigger = await self._sensor.latest_trigger()
        except Exception:  # pylint: disable=broad-except
            last_trigger = None
            _LOGGER.exception("failed to update motion sensor")

        if not last_trigger:
            return

        has_timed_out = datetime.now() > last_trigger + timedelta(seconds=self._timeout)
        if has_timed_out:
            if self._on:
                self._on = False
                self.hass.async_add_job(self.async_update_ha_state(True))
        else:
            if not self._on:
                self._on = True
                self.hass.async_add_job(self.async_update_ha_state(True))


class DlinkWaterSensor(DlinkBinarySensor):
    """Representation of a D-Link water sensor."""

    def __init__(self, name, sensor):
        """Initialize the D-Link motion binary sensor."""
        super().__init__(name, sensor, DEVICE_CLASS_MOISTURE)

    async def async_update(self):
        """Get the latest data and updates the states."""
        try:
            water_detected = await self._sensor.water_detected()
            if self._on != water_detected:
                self._on = water_detected
                self.hass.async_add_job(self.async_update_ha_state(True))

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("failed to update water sensor")
