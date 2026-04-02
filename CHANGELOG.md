# Changelog

**Version 2.0.0**

* Added UI config flow with manual setup and SSDP auto-discovery
* Added options flow for configurable scan interval and motion timeout
* Added DataUpdateCoordinator for centralized polling
* Added temperature sensor support
* Added firmware version diagnostic sensor
* Added device info (manufacturer, model, firmware version, hardware version)
* Added diagnostics support with sensitive data redaction
* Added English translations
* Migrated from legacy platform setup to modern integration architecture
* Automatic migration from YAML configuration to config entries
* Bumped minimum Home Assistant version to 2024.4.0

*Fixes:*
* Fixed deprecated `DEVICE_CLASS_*` imports causing load failure on HA 2025.1+ ([Upstream #18](https://github.com/postlund/dlink_hnap/issues/18))
* Fixed excessive error logging when device is in power-saving mode or unreachable ([Upstream #12](https://github.com/postlund/dlink_hnap/issues/12))
* Fixed missing device health/availability indication ([Upstream #17](https://github.com/postlund/dlink_hnap/issues/17))
* Fixed compatibility issues with Home Assistant 2025.2.x ([Upstream #21](https://github.com/postlund/dlink_hnap/issues/21))

**Version 0.2.0**

* Added support for water leakage sensor (DCH-S160)
* Breaking change: `type` must be set (see README.md)

**Initial version**
