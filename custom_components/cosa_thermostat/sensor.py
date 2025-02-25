"""Support for Cosa Thermostat sensors."""
from __future__ import annotations
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Sensör tanımlamaları
SENSORS = [
    SensorEntityDescription(
        key="combi_state",
        name="Combi State",
        icon="mdi:radiator",
    ),
    SensorEntityDescription(
        key="current_temperature",
        name="Current Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="target_temperature",
        name="Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-check",
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
]

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Cosa Thermostat sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    device_id = config_entry.data["device_id"]
    
    try:
        entities = []
        for description in SENSORS:
            _LOGGER.debug("Creating sensor with description: %s", description)
            entities.append(
                CosaThermostatSensor(
                    coordinator,
                    description,
                    device_id
                )
            )
        
        async_add_entities(entities, False)
        _LOGGER.debug("Added %s sensor entities", len(entities))
        
    except Exception as ex:
        _LOGGER.error("Error setting up sensors: %s", ex)

class CosaThermostatSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Cosa Thermostat sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_has_entity_name = True
        
        _LOGGER.debug(
            "Initialized sensor: %s with unique_id: %s",
            description.name,
            self._attr_unique_id
        )

    @property
    def native_value(self) -> str | float | None:
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data:
                return None

            data = self.coordinator.data
            endpoint = data.get("endpoint", {})
            
            if self.entity_description.key == "combi_state":
                combi_state = endpoint.get("combiState", "unknown")
                operation_mode = endpoint.get("operationMode")
                
                if combi_state == "on" and operation_mode == "heating":
                    return "heating"
                elif combi_state == "off":
                    return "off"
                else:
                    return "idle"
                    
            elif self.entity_description.key == "current_temperature":
                temp = endpoint.get("temperature")
                return float(temp) if temp is not None else None
                
            elif self.entity_description.key == "target_temperature":
                current_option = endpoint.get("option")
                if current_option:
                    temp = endpoint.get(f"{current_option}Temperature")
                    return float(temp) if temp is not None else None
                return None
                
            elif self.entity_description.key == "humidity":
                humidity = endpoint.get("humidity")
                return float(humidity) if humidity is not None else None
                
        except Exception as ex:
            _LOGGER.error(
                "Error getting value for sensor %s: %s",
                self.entity_description.key,
                ex
            )
            return None 