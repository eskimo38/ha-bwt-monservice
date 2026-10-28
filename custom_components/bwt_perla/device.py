"""Shared device-registry information for BWT Mon Service entities."""
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    BWT_DEVICE_URL,
    CONF_DEVICE_NAME,
    CONF_SERIAL_NUMBER,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    MANUFACTURER,
)


def build_device_info(entry, data: dict | None, receipt_line_key: str | None) -> DeviceInfo:
    """Build DeviceInfo from the config entry and the latest coordinator data."""
    data = data or {}
    serial = entry.data[CONF_SERIAL_NUMBER]
    url = f"{BWT_DEVICE_URL}?receiptLineKey={receipt_line_key}" if receipt_line_key else None
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        name=entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME),
        manufacturer=MANUFACTURER,
        model="My Perla Optimum",
        model_id=data.get("product_code"),
        serial_number=serial,
        sw_version=data.get("firmware_cpu"),
        configuration_url=url,
    )
