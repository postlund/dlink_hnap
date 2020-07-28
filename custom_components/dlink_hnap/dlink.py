#!/usr/bin/env python3
"""Read data from D-Link motion sensor."""

import sys
import hmac
import logging
import asyncio

import xml
import xml.etree.ElementTree as ET

from io import BytesIO
from datetime import datetime

import xmltodict
import aiohttp

_LOGGER = logging.getLogger(__name__)

ACTION_BASE_URL = "http://purenetworks.com/HNAP1/"


def _hmac(key, message):
    return (
        hmac.new(key.encode("utf-8"), message.encode("utf-8"), digestmod="MD5")
        .hexdigest()
        .upper()
    )


class AuthenticationError(Exception):
    """Thrown when login fails."""


class HNAPClient:
    """Client for the HNAP protocol."""

    def __init__(self, soap, username, password):
        """Initialize a new HNAPClient instance."""
        self.username = username
        self.password = password
        self._client = soap
        self._private_key = None
        self._cookie = None
        self._auth_token = None
        self._timestamp = None

    async def login(self):
        """Authenticate with device and obtain cookie."""
        _LOGGER.info("Logging into device")
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

        except xml.parsers.expat.ExpatError:
            raise AuthenticationError("Bad response from device")

    async def call(self, method, *_, **kwargs):
        """Call an NHAP method (async)."""
        # Do login if no login has been done before
        if not self._private_key and method != "Login":
            await self.login()

        self._update_nauth_token(method)
        try:
            result = await self.soap().call(method, **kwargs)
            if "ERROR" in result:
                self._bad_response()
        except Exception:  # pylint: disable=broad-except
            self._bad_response()
        return result

    async def soap_actions(self, module_id):
        """Return supported SOAP actions."""
        resp = await self.call("GetDeviceSettings", ModuleID=module_id)
        actions = resp["SOAPActions"]["string"]
        return [x[x.rfind("/") + 1 :] for x in actions]

    def _bad_response(self):
        _LOGGER.error("Got an error, resetting private key")
        self._private_key = None
        raise Exception("got error response from device")

    def _update_nauth_token(self, action):
        """Update NHAP auth token for an action."""
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

    def soap(self):
        """Get SOAP client with updated headers."""
        if self._cookie:
            self._client.headers["Cookie"] = "uid={0}".format(self._cookie)
        if self._auth_token:
            self._client.headers["HNAP_AUTH"] = "{0} {1}".format(
                self._auth_token, self._timestamp
            )

        return self._client


class BaseSensor:
    """Wrapper class for a sensor."""

    def __init__(self, client, module_id=1):
        """Initialize a new BaseSensor instance."""
        self.client = client
        self.module_id = module_id
        self._settings = {}
        self._soap_actions = []

    @property
    def vendor(self):
        """Return device vendor name."""
        return self._settings.get("VendorName")

    @property
    def model(self):
        """Return model name."""
        return self._settings.get("ModelName")

    @property
    def model_description(self):
        """Return model description."""
        return self._settings.get("ModelDescription")

    @property
    def firmware(self):
        """Return installed firmwware version."""
        return self._settings.get("FirmwareVersion")

    @property
    def hardware(self):
        """Return hardware revision."""
        return self._settings.get("HardwareVersion")

    @property
    def mac(self):
        """Return device MAC address."""
        return self._settings.get("DeviceMacId")

    async def _init(self):
        if not self._settings:
            self._settings = await self.client.call("GetDeviceSettings")

        if not self._soap_actions:
            self._soap_actions = await self.client.soap_actions(self.module_id)

            print("actions:", self._soap_actions)

    async def latest_trigger(self):
        """Get latest trigger time from sensor."""
        await self._init()

        if "GetLatestDetection" in self._soap_actions:
            resp = await self.client.call("GetLatestDetection", ModuleID=self.module_id)
            detect_time = resp["LatestDetectTime"]
        else:
            resp = await self.client.call(
                "GetMotionDetectorLogs",
                ModuleID=self.module_id,
                MaxCount=1,
                PageOffset=1,
                StartTime=0,
                EndTime="All",
            )
            if "MotionDetectorLogList" not in resp:
                _LOGGER.exception("log list: %s", resp)
            log_list = resp["MotionDetectorLogList"]
            detect_time = log_list["MotionDetectorLog"]["TimeStamp"]

        return datetime.fromtimestamp(float(detect_time))


class MotionSensor(BaseSensor):
    """Wrapper class for motion sensor."""


class WaterSensor(BaseSensor):
    """Wrapper class for water detect sensor."""

    async def water_detected(self):
        """Get latest trigger time from sensor."""
        await self._init()
        resp = await self.client.call("GetWaterDetectorState", ModuleID=self.module_id)
        return resp.get("IsWater") == "true"


class NanoSOAPClient:  # pylint: disable=too-few-public-methods
    """Minimalistic SOAP client."""

    BASE_NS = {
        "xmlns:soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    ACTION_NS = {"xmlns": "http://purenetworks.com/HNAP1/"}

    def __init__(self, address, action, session):
        self.address = "http://{0}/HNAP1".format(address)
        self.action = action
        self.session = session
        self.headers = {}

    def _generate_request_xml(self, method, **kwargs):
        body = ET.Element("soap:Body")
        action = ET.Element(method, self.ACTION_NS)
        body.append(action)

        for param, value in kwargs.items():
            element = ET.Element(param)
            element.text = str(value)
            action.append(element)

        envelope = ET.Element("soap:Envelope", self.BASE_NS)
        envelope.append(body)

        data = BytesIO()
        tree = ET.ElementTree(envelope)
        tree.write(data, encoding="utf-8", xml_declaration=True)

        return data.getvalue().decode("utf-8")

    async def call(self, method, **kwargs):
        """Call a SOAP action."""
        data = self._generate_request_xml(method, **kwargs)

        headers = self.headers.copy()
        headers["SOAPAction"] = '"{0}{1}"'.format(self.action, method)

        resp = await self.session.post(
            self.address, data=data, headers=headers, timeout=10
        )
        text = await resp.text()
        parsed = xmltodict.parse(text)
        if "soap:Envelope" not in parsed:
            _LOGGER.exception("parsed: %s", parsed)
            raise Exception("probably a bad response")

        return parsed["soap:Envelope"]["soap:Body"][method + "Response"]


async def main():
    """Script starts here."""
    logging.basicConfig(level=logging.DEBUG)

    address = sys.argv[1]
    pin = sys.argv[2]
    cmd = sys.argv[3]

    async with aiohttp.ClientSession() as session:
        soap = NanoSOAPClient(address, ACTION_BASE_URL, session)
        client = HNAPClient(soap, "Admin", pin)

        if cmd == "latest_motion":
            latest = await BaseSensor(client).latest_trigger()
            print("Latest time:", latest)
        elif cmd == "water_detected":
            latest = await WaterSensor(client).water_detected()
            print("Water detected: " + str(latest))
        elif cmd == "actions":
            print("Supported actions:")
            actions = await client.soap_actions(module_id=1)
            print("\n".join(actions))
        elif cmd == "log":
            resp = await client.call(
                "GetSystemLogs", MaxCount=100, PageOffset=1, StartTime=0, EndTime="All"
            )
            print(resp)
        else:
            print(await client.call(cmd))


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
