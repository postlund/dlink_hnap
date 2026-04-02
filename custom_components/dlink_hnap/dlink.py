#!/usr/bin/env python3
"""D-Link HNAP protocol client and sensor helpers."""

from __future__ import annotations

import xml
import hmac
import logging
import asyncio
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime
from typing import Any

import aiohttp
import xmltodict

_LOGGER = logging.getLogger(__name__)

ACTION_BASE_URL = "http://purenetworks.com/HNAP1/"


def _hmac(key: str, message: str) -> str:
    return (
        hmac.new(key.encode("utf-8"), message.encode("utf-8"), digestmod="MD5")
        .hexdigest()
        .upper()
    )


class AuthenticationError(Exception):
    """Thrown when login fails."""


class CannotConnect(Exception):
    """Thrown when device is unreachable."""


class HNAPClient:
    """Client for the HNAP protocol."""

    def __init__(
        self,
        soap: NanoSOAPClient,
        username: str,
        password: str,
    ) -> None:
        """Initialize a new HNAPClient instance."""
        self.username = username
        self.password = password
        self.logged_in = False
        self.actions: list[str] | None = None
        self._client = soap
        self._private_key: str | None = None
        self._cookie: str | None = None
        self._auth_token: str | None = None
        self._timestamp: int | None = None
        self._device_settings: dict[str, Any] | None = None

    async def login(self) -> None:
        """Authenticate with device and obtain cookie."""
        _LOGGER.info("Logging into device")
        self.logged_in = False
        resp = await self.call(
            "Login",
            Action="request",
            Username=self.username,
            LoginPassword="",
            Captcha="",
        )

        challenge = resp["Challenge"]
        public_key = resp["PublicKey"]
        self._cookie = resp["Cookie"]
        _LOGGER.debug(
            "Challenge: %s, Public key: %s, Cookie: %s",
            challenge,
            public_key,
            self._cookie,
        )

        self._private_key = _hmac(public_key + str(self.password), challenge)
        _LOGGER.debug("Private key: %s", self._private_key)

        try:
            password = _hmac(self._private_key, challenge)
            resp = await self.call(
                "Login",
                Action="login",
                Username=self.username,
                LoginPassword=password,
                Captcha="",
            )

            if resp["LoginResult"].lower() != "success":
                raise AuthenticationError("Incorrect username or password")

            if not self.actions:
                self.actions = await self._fetch_device_actions()

        except xml.parsers.expat.ExpatError as err:
            raise AuthenticationError("Bad response from device") from err

        self.logged_in = True

    async def _fetch_device_actions(self) -> list[str]:
        """Fetch supported SOAP actions from device."""
        settings = await self._get_device_settings_raw()
        return list(
            map(lambda x: x[x.rfind("/") + 1 :], settings["SOAPActions"]["string"])
        )

    async def _get_device_settings_raw(self) -> dict[str, Any]:
        """Fetch and cache raw GetDeviceSettings response."""
        if self._device_settings is None:
            self._device_settings = await self.call("GetDeviceSettings")
        return self._device_settings

    async def soap_actions(self, module_id: int) -> dict[str, Any]:
        """Get SOAP actions for a module."""
        return await self.call("GetModuleSOAPActions", ModuleID=module_id)

    async def call(self, method: str, **kwargs: Any) -> dict[str, Any]:
        """Call an HNAP method (async)."""
        if not self._private_key and method != "Login":
            await self.login()

        self._update_nauth_token(method)
        try:
            result = await self._get_soap_client().call(method, **kwargs)
            if "ERROR" in result:
                self._bad_response()
        except (AuthenticationError, CannotConnect):
            raise
        except Exception:
            self._bad_response()
        return result

    def _bad_response(self) -> None:
        _LOGGER.error("Got an error, resetting private key")
        self._private_key = None
        self._device_settings = None
        raise CannotConnect("Got error response from device")

    def _update_nauth_token(self, action: str) -> None:
        """Update HNAP auth token for an action."""
        if not self._private_key:
            return

        self._timestamp = int(datetime.now().timestamp())
        self._auth_token = _hmac(
            self._private_key,
            '{0}"{1}{2}"'.format(self._timestamp, ACTION_BASE_URL, action),
        )
        _LOGGER.debug(
            "Generated new token for %s: %s (time: %d)",
            action,
            self._auth_token,
            self._timestamp,
        )

    def _get_soap_client(self) -> NanoSOAPClient:
        """Get SOAP client with updated headers."""
        if self._cookie:
            self._client.headers["Cookie"] = "uid={0}".format(self._cookie)
        if self._auth_token:
            self._client.headers["HNAP_AUTH"] = "{0} {1}".format(
                self._auth_token, self._timestamp
            )
        return self._client

    # ── High-level API methods for the coordinator ──────────────────────

    async def test_connection(self) -> dict[str, Any]:
        """Validate connection and credentials. Returns device info on success.

        Raises AuthenticationError or CannotConnect on failure.
        """
        await self.login()
        return await self.get_device_info()

    async def get_device_info(self) -> dict[str, Any]:
        """Return device metadata (model, firmware, serial, name)."""
        settings = await self._get_device_settings_raw()
        return {
            "model": settings.get("ModelName", "Unknown"),
            "device_name": settings.get("DeviceName", "D-Link Sensor"),
            "firmware": settings.get("FirmwareVersion", "Unknown"),
            "hardware_version": settings.get("HardwareVersion", ""),
            "serial": settings.get("DeviceMacId", settings.get("MacAddress", "")),
        }

    async def get_module_soap_actions(self, module_id: int = 1) -> list[str]:
        """Return list of SOAP action names for a module."""
        resp = await self.soap_actions(module_id)
        actions = resp.get("ModuleSOAPList", {}).get("SOAPActions", {}).get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        return actions

    async def get_water_state(self, module_id: int = 1) -> bool:
        """Return True if water is detected."""
        resp = await self.call("GetWaterDetectorState", ModuleID=module_id)
        return resp.get("IsWater") == "true"

    async def get_latest_motion(self, module_id: int = 1) -> datetime | None:
        """Return timestamp of latest motion event, or None."""
        module_actions = await self.get_module_soap_actions(module_id)

        detect_time = None
        if "GetLatestDetection" in module_actions:
            resp = await self.call("GetLatestDetection", ModuleID=module_id)
            detect_time = resp.get("LatestDetectTime")
        else:
            resp = await self.call(
                "GetMotionDetectorLogs",
                ModuleID=module_id,
                MaxCount=1,
                PageOffset=1,
                StartTime=0,
                EndTime="All",
            )
            log_list = resp.get("MotionDetectorLogList", {})
            log_entry = log_list.get("MotionDetectorLog", {})
            detect_time = log_entry.get("TimeStamp")

        if detect_time is not None:
            try:
                return datetime.fromtimestamp(float(detect_time))
            except (ValueError, TypeError, OSError):
                _LOGGER.warning("Invalid motion detect time: %s", detect_time)
        return None

    async def get_temperature(self, module_id: int = 1) -> float | None:
        """Return temperature in Celsius, or None if unavailable."""
        try:
            resp = await self.call("GetCurrentTemperature", ModuleID=module_id)
            value = resp.get("CurrentTemperature")
            if value is not None:
                return float(value)
        except Exception:
            _LOGGER.debug("Temperature not available from device")
        return None

    async def get_all_data(
        self,
        capabilities: set[str],
        module_id: int = 1,
        motion_timeout: int = 30,
    ) -> dict[str, Any]:
        """Fetch all sensor data in one coordinated call.

        Only fetches data for the given capabilities to avoid unnecessary calls.
        """
        data: dict[str, Any] = {}

        if "water" in capabilities:
            try:
                data["water_detected"] = await self.get_water_state(module_id)
            except Exception:
                _LOGGER.debug("Failed to get water state", exc_info=True)
                data["water_detected"] = None

        if "motion" in capabilities:
            try:
                last_motion = await self.get_latest_motion(module_id)
                data["last_motion"] = last_motion
                if last_motion is not None:
                    elapsed = (datetime.now() - last_motion).total_seconds()
                    data["motion_detected"] = elapsed <= motion_timeout
                else:
                    data["motion_detected"] = False
            except Exception:
                _LOGGER.debug("Failed to get motion state", exc_info=True)
                data["motion_detected"] = None
                data["last_motion"] = None

        if "temperature" in capabilities:
            data["temperature"] = await self.get_temperature(module_id)

        # Device info is always fetched
        try:
            info = await self.get_device_info()
            data.update(info)
        except Exception:
            _LOGGER.debug("Failed to refresh device info", exc_info=True)

        return data

    async def detect_capabilities(self, module_id: int = 1) -> set[str]:
        """Probe device to discover available capabilities."""
        capabilities: set[str] = set()

        # Get device-level actions
        if not self.actions:
            await self.login()

        device_actions = self.actions or []

        # Get module-level actions
        try:
            module_actions = await self.get_module_soap_actions(module_id)
        except Exception:
            module_actions = []

        all_actions = set(device_actions) | set(module_actions)

        if "GetWaterDetectorState" in all_actions:
            capabilities.add("water")
        if "GetLatestDetection" in all_actions or "GetMotionDetectorLogs" in all_actions:
            capabilities.add("motion")
        if "GetCurrentTemperature" in all_actions:
            capabilities.add("temperature")

        _LOGGER.info("Detected capabilities: %s (from %d actions)", capabilities, len(all_actions))
        return capabilities


class NanoSOAPClient:
    """Lightweight async SOAP client for HNAP."""

    BASE_NS = {
        "xmlns:soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    ACTION_NS = {"xmlns": "http://purenetworks.com/HNAP1/"}

    def __init__(self, address: str, action: str, session: aiohttp.ClientSession) -> None:
        self.address = f"http://{address}/HNAP1"
        self.action = action
        self.session = session
        self.headers: dict[str, str] = {}

    def _generate_request_xml(self, method: str, **kwargs: Any) -> str:
        body = ET.Element("soap:Body")
        action = ET.Element(method, self.ACTION_NS)
        body.append(action)

        for param, value in kwargs.items():
            element = ET.Element(param)
            element.text = str(value)
            action.append(element)

        envelope = ET.Element("soap:Envelope", self.BASE_NS)
        envelope.append(body)

        f = BytesIO()
        tree = ET.ElementTree(envelope)
        tree.write(f, encoding="utf-8", xml_declaration=True)

        return f.getvalue().decode("utf-8")

    async def call(self, method: str, **kwargs: Any) -> dict[str, Any]:
        """Make an HNAP SOAP call."""
        request_xml = self._generate_request_xml(method, **kwargs)

        headers = self.headers.copy()
        headers["SOAPAction"] = '"{0}{1}"'.format(self.action, method)

        try:
            async with asyncio.timeout(10):
                resp = await self.session.post(
                    self.address, data=request_xml, headers=headers,
                )
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise CannotConnect(f"Cannot reach device at {self.address}") from err

        try:
            parsed = xmltodict.parse(text)
        except Exception as err:
            raise CannotConnect(f"Invalid XML response from device") from err

        if "soap:Envelope" not in parsed:
            _LOGGER.error("Unexpected response: %s", str(parsed)[:200])
            raise CannotConnect("Unexpected response from device")

        return parsed["soap:Envelope"]["soap:Body"][method + "Response"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    import sys

    address = sys.argv[1]
    pin = sys.argv[2]
    cmd = sys.argv[3]

    async def _main() -> None:
        session = aiohttp.ClientSession()
        try:
            soap = NanoSOAPClient(address, ACTION_BASE_URL, session=session)
            client = HNAPClient(soap, "Admin", pin)
            await client.login()

            if cmd == "latest_motion":
                latest = await client.get_latest_motion()
                print("Latest time: " + str(latest))
            elif cmd == "water_detected":
                detected = await client.get_water_state()
                print("Water detected: " + str(detected))
            elif cmd == "actions":
                print("Supported actions:")
                print("\n".join(client.actions or []))
            elif cmd == "capabilities":
                caps = await client.detect_capabilities()
                print("Capabilities: " + str(caps))
            elif cmd == "info":
                info = await client.get_device_info()
                for k, v in info.items():
                    print(f"  {k}: {v}")
            elif cmd == "temperature":
                temp = await client.get_temperature()
                print("Temperature: " + str(temp))
        finally:
            await session.close()

    asyncio.run(_main())
