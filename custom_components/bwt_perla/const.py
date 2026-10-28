"""Constants for BWT Mon Service integration."""
from datetime import timedelta

DOMAIN = "bwt_perla"
MANUFACTURER = "BWT"

# Configuration
CONF_SERIAL_NUMBER = "serial_number"
CONF_DEVICE_NAME = "device_name"
CONF_INTERVAL_MAIN = "interval_main"
CONF_INTERVAL_CONSUMPTION = "interval_consumption"

# Defaults
DEFAULT_DEVICE_NAME = "BWT My Perla Optimum"
DEFAULT_INTERVAL_MAIN = 3600  # 1 hour
DEFAULT_INTERVAL_CONSUMPTION = 60  # 1 minute

# Update intervals
UPDATE_INTERVAL_MAIN = timedelta(seconds=3600)
UPDATE_INTERVAL_CONSUMPTION = timedelta(seconds=300)

# API URLs
BWT_BASE_URL = "https://www.bwt-monservice.com"
BWT_LOGIN_URL = f"{BWT_BASE_URL}/login"
BWT_DASHBOARD_URL = f"{BWT_BASE_URL}/dashboard"
BWT_DEVICE_URL = f"{BWT_BASE_URL}/device"
BWT_SUMMARY_URL = f"{BWT_BASE_URL}/ajax/product-summary"
BWT_LOAD_CONSO_URL = f"{BWT_BASE_URL}/_components/DeviceTabs/loadConso"

# Entity keys fed by the consumption (loadConso) endpoint. Every other key comes
# from the main product-summary endpoint. Used to mark only the affected group
# of entities unavailable when one of the two endpoints fails.
GROUP_MAIN = "main"
GROUP_CONSUMPTION = "consumption"
CONSUMPTION_KEYS = frozenset(
    {
        "water_consumption",
        "water_increment",
        "regen_count",
        "salt_consumption",
        "last_update",
        "refresh_date",
        "salt_alarm",
        "power_outage",
    }
)

# Sensor types
SENSOR_TYPES = {
    "salt": {
        "name": "Salt per Regeneration",
        "unit": "g",
        "icon": "mdi:shaker",
        "device_class": "weight",
        "state_class": "measurement",
        "diagnostic": True,
    },
    "resin_vol": {
        "name": "Resin Volume",
        "unit": "L",
        "icon": "mdi:water",
        "device_class": None,
        "state_class": "measurement",
        "diagnostic": True,
    },
    "in_hardness": {
        "name": "Inlet Hardness",
        "unit": "°f",
        "icon": "mdi:water-opacity",
        "device_class": None,
        "state_class": "measurement",
    },
    "out_hardness": {
        "name": "Outlet Hardness",
        "unit": "°f",
        "icon": "mdi:water-check",
        "device_class": None,
        "state_class": "measurement",
    },
    "pressure": {
        "name": "Pressure",
        "unit": "bar",
        "icon": "mdi:gauge",
        "device_class": "pressure",
        "state_class": "measurement",
    },
    "wifi_signal": {
        "name": "WiFi Signal",
        "unit": "dBm",
        "icon": "mdi:wifi",
        "device_class": "signal_strength",
        "state_class": "measurement",
        "diagnostic": True,
    },
    "vol_ok": {
        "name": "Softened Water Volume",
        "unit": "L",
        "icon": "mdi:water-check",
        "device_class": "water",
        "state_class": "total",
    },
    "reserve_volume": {
        "name": "Reserve Volume",
        "unit": "L",
        "icon": "mdi:water-percent",
        "device_class": None,
        "state_class": "measurement",
        "diagnostic": True,
    },
    "regen_time": {
        "name": "Regeneration Time",
        "unit": None,
        "icon": "mdi:clock-start",
        "device_class": None,
        "state_class": None,
        "diagnostic": True,
    },
    "salt_type": {
        "name": "Salt Type",
        "unit": None,
        "icon": "mdi:shaker",
        "device_class": None,
        "state_class": None,
        "diagnostic": True,
    },
    "firmware_cpu": {
        "name": "Controller Firmware",
        "unit": None,
        "icon": "mdi:chip",
        "device_class": None,
        "state_class": None,
        "diagnostic": True,
    },
    "firmware_iot": {
        "name": "Wi-Fi Module Firmware",
        "unit": None,
        "icon": "mdi:wifi-cog",
        "device_class": None,
        "state_class": None,
        "diagnostic": True,
    },
    "water_consumption": {
        "name": "Water Consumption",
        "unit": "L",
        "icon": "mdi:water",
        "device_class": "water",
        "state_class": "total_increasing",
    },
    "water_increment": {
        "name": "Water Increment",
        "unit": "L",
        "icon": "mdi:water-plus",
        "device_class": None,
        "state_class": "measurement",
    },
    "regen_count": {
        "name": "Regenerations",
        "unit": "",
        "icon": "mdi:refresh",
        "device_class": None,
        "state_class": "total_increasing",
    },
    "salt_consumption": {
        "name": "Salt Consumption",
        "unit": "g",
        "icon": "mdi:shaker-outline",
        "device_class": "weight",
        "state_class": "total_increasing",
    },
    "last_update": {
        "name": "Last Measurement Date",
        "unit": None,
        "icon": "mdi:calendar-clock",
        "device_class": "timestamp",
        "state_class": None,
        "diagnostic": True,
    },
    "refresh_date": {
        "name": "Last Data Refresh",
        "unit": None,
        "icon": "mdi:update",
        "device_class": "timestamp",
        "state_class": None,
        "diagnostic": True,
    },
}

BINARY_SENSOR_TYPES = {
    "online": {
        "name": "Online",
        "device_class": "connectivity",
        "icon": "mdi:lan-connect",
        "diagnostic": True,
    },
    "standby": {
        "name": "Holiday Mode",
        "device_class": "running",
        "icon": "mdi:power-sleep",
    },
    "salt_alarm": {
        "name": "Salt Alarm",
        "device_class": "problem",
        "icon": "mdi:alert",
    },
    "power_outage": {
        "name": "Power Outage",
        "device_class": "problem",
        "icon": "mdi:power-plug-off",
    },
}
