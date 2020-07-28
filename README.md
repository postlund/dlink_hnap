![Validate with hassfest](https://github.com/postlund/dlink_hnap/workflows/Validate%20with%20hassfest/badge.svg)
![HACS Validation](https://github.com/postlund/dlink_hnap/workflows/HACS%20Validation/badge.svg)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# D-Link HNAP

This is an experimental integration to Home Assistant supporting D-Link devices. It communicates
locally with the devices, i.e. no cloud needed, but only supports polling.

The following devices are supported:

* Motion Sensor (DCH-S150)
* Water Leakage Sensor (DCH-S160)

*DISCLAIMER: Currently I don't use any of these devices. So I cannot test the integration. It is
provided as reference and for the community to maintain. Please send PRs!*

## Installation

### HACS _(preferred method)_

This integration is available in the default repository list, just search for it!

### Manual install

Place the `custom_components` folder in your configuration directory
(or add its contents to an existing `custom_components` folder).

## Configuration

This integration does not support config flows yet, so you need to add
it in `configuration.yaml`:

```yaml
binary_sensor:
  - platform: dlink_hnap
    name: Kitchen Motion
    host: 10.0.0.10
    type: motion
    username: Admin
    password: 123456
    timeout: 35
  - platform: dlink_hnap
    name: Kitchen Leakage
    host: 10.0.0.11
    type: water
    username: Admin
    password: 123456
```

Here are the configuration options:

key | optional | type | default | description
-- | -- | -- | -- | --
`name` | True | string | D-Link Motion Sensor | Name for the sensor
`type` | False | string | | Sensor type: motion or water
`host` | False | string | | IP address to sensor
`username` | True | string | Admin | Username for authentication (always Admin)
`password` | False | int | | PIN code written on the device
`timeout` | True | int | 35 | Amount of seconds before sensor going to `off` after *last* motion (only used when `type` is `motion`)
