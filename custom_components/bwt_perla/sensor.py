"""Sensor platform for BWT Mon Service integration."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    SENSOR_TYPES,
    CONF_SERIAL_NUMBER,
    CONF_DEVICE_NAME,
    DEFAULT_DEVICE_NAME,
)
from .coordinator import BWTDataUpdateCoordinator
from .device import build_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BWT Mon Service sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        BWTSensor(coordinator, entry, sensor_type) for sensor_type in SENSOR_TYPES
    )


class BWTSensor(CoordinatorEntity, SensorEntity):
    """Representation of a BWT sensor."""

    def __init__(
        self,
        coordinator: BWTDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._serial_number = entry.data[CONF_SERIAL_NUMBER]
        self._device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
        self._attr_unique_id = f"{self._serial_number}_{sensor_type}"

        sensor_info = SENSOR_TYPES[sensor_type]
        self._attr_has_entity_name = True
        self._attr_name = sensor_info["name"]
        self._attr_native_unit_of_measurement = sensor_info["unit"]
        self._attr_icon = sensor_info["icon"]
        self._attr_device_class = sensor_info.get("device_class")
        self._attr_state_class = sensor_info.get("state_class")
        if sensor_info.get("diagnostic"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._entry = entry
        self._attr_device_info = build_device_info(
            entry, coordinator.data, coordinator.receipt_line_key
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_type)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.key_available(self._sensor_type)
        )
