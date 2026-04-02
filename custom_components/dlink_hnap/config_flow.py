"""Config flow for D-Link HNAP integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from homeassistant.components.ssdp import SsdpServiceInfo

from .const import (
    DEFAULT_MOTION_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class DLinkHNAPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for D-Link HNAP."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DLinkHNAPOptionsFlow:
        """Get the options flow for this handler."""
        return DLinkHNAPOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual setup by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await self._async_validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                unique_id = info["serial"]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info.get("device_name", "D-Link Sensor"),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> FlowResult:
        """Handle SSDP discovery."""
        _LOGGER.debug("SSDP discovery info: %s", discovery_info)

        # Extract host from SSDP location URL
        from urllib.parse import urlparse

        location = discovery_info.ssdp_location or ""
        parsed = urlparse(location)
        host = parsed.hostname

        if not host:
            return self.async_abort(reason="no_host")

        # Use UDN or serial as unique id
        upnp = discovery_info.upnp or {}
        unique_id = discovery_info.ssdp_usn or upnp.get("serialNumber", "")
        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._discovered_host = host
        self._discovered_name = upnp.get("friendlyName", f"D-Link ({host})")

        self.context["title_placeholders"] = {"name": self._discovered_name}

        return await self.async_step_credentials()

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle credentials input after SSDP discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            full_input = {
                CONF_HOST: self._discovered_host,
                **user_input,
            }
            try:
                info = await self._async_validate_input(full_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                # Update unique_id with device serial if we got a better one
                if info.get("serial"):
                    await self.async_set_unique_id(info["serial"])
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info.get("device_name", self._discovered_name or "D-Link Sensor"),
                    data=full_input,
                )

        return self.async_show_form(
            step_id="credentials",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            errors=errors,
            description_placeholders={
                "host": self._discovered_host or "",
                "name": self._discovered_name or "",
            },
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> FlowResult:
        """Handle import from YAML configuration."""
        return await self.async_step_user(import_data)

    async def _async_validate_input(
        self, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate user input by connecting to the device."""
        session = async_get_clientsession(self.hass)
        soap = NanoSOAPClient(data[CONF_HOST], ACTION_BASE_URL, session=session)
        client = HNAPClient(soap, data[CONF_USERNAME], data[CONF_PASSWORD])
        return await client.test_connection()


class DLinkHNAPOptionsFlow(OptionsFlow):
    """Handle options flow for D-Link HNAP."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            "scan_interval", int(DEFAULT_SCAN_INTERVAL.total_seconds())
        )
        current_motion_timeout = self.config_entry.options.get(
            "motion_timeout", DEFAULT_MOTION_TIMEOUT
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("scan_interval", default=current_interval): vol.All(
                        int, vol.Range(min=5, max=300)
                    ),
                    vol.Optional(
                        "motion_timeout", default=current_motion_timeout
                    ): vol.All(int, vol.Range(min=5, max=600)),
                }
            ),
        )
