"""BWT Mon Service integration for Home Assistant."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.const import Platform

from .const import CONF_SERIAL_NUMBER, DOMAIN
from .device import build_device_info
from .coordinator import BWTDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BWT Mon Service from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = BWTDataUpdateCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await coordinator.async_shutdown()
        raise

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Keep device registry fields (firmware, product code) in sync with BWT
    @callback
    def _sync_device_registry() -> None:
        dev_reg = dr.async_get(hass)
        serial = entry.data[CONF_SERIAL_NUMBER]
        device = dev_reg.async_get_device(identifiers={(DOMAIN, serial)})
        if device is None:
            return
        info = build_device_info(entry, coordinator.data, coordinator.receipt_line_key)
        updates = {}
        if info.get("sw_version") and info["sw_version"] != device.sw_version:
            updates["sw_version"] = info["sw_version"]
        if info.get("model_id") and info["model_id"] != device.model_id:
            updates["model_id"] = info["model_id"]
        if info.get("configuration_url") and str(info["configuration_url"]) != str(
            device.configuration_url
        ):
            updates["configuration_url"] = info["configuration_url"]
        if updates:
            dev_reg.async_update_device(device.id, **updates)

    _sync_device_registry()
    entry.async_on_unload(coordinator.async_add_listener(_sync_device_registry))

    # Reload when options change so new intervals take effect
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after the options flow saved new values."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok
