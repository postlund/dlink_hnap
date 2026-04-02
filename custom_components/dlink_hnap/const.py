"""Constants for the D-Link HNAP integration."""
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "dlink_hnap"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_SERIAL = "serial"

DEFAULT_USERNAME = "Admin"
DEFAULT_PASSWORD = ""
DEFAULT_TIMEOUT = 30
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_MOTION_TIMEOUT = 30

# HNAP action names used for capability detection
HNAP_ACTION_WATER = "GetWaterDetectorState"
HNAP_ACTION_MOTION_LATEST = "GetLatestDetection"
HNAP_ACTION_MOTION_LOGS = "GetMotionDetectorLogs"
HNAP_ACTION_TEMPERATURE = "GetCurrentTemperature"
HNAP_ACTION_SYSTEM_LOGS = "GetSystemLogs"

# Coordinator data keys
KEY_WATER_DETECTED = "water_detected"
KEY_MOTION_DETECTED = "motion_detected"
KEY_LAST_MOTION = "last_motion"
KEY_TEMPERATURE = "temperature"
KEY_BATTERY = "battery"
KEY_FIRMWARE = "firmware"
KEY_MODEL = "model"
KEY_SERIAL = "serial"
KEY_DEVICE_NAME = "device_name"
KEY_HARDWARE_VERSION = "hardware_version"
KEY_AVAILABLE_CAPABILITIES = "available_capabilities"

# Capability identifiers
CAP_WATER = "water"
CAP_MOTION = "motion"
CAP_TEMPERATURE = "temperature"
