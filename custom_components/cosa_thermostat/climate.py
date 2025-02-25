"""Support for Cosa Thermostat."""
from __future__ import annotations

import logging
import asyncio
from typing import Any
from datetime import timedelta

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    API_BASE_URL,
    API_SET_TARGET_TEMPERATURES,
    API_SET_MODE,
    API_SET_OPTION,
    API_SET_OPERATION_MODE,
)

_LOGGER = logging.getLogger(__name__)

# Her 30 saniyede bir güncelleme yap
SCAN_INTERVAL = timedelta(seconds=10)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Cosa Thermostat climate device."""
    _LOGGER.debug("Setting up Cosa Thermostat climate entity")
    
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    device_id = config_entry.data["device_id"]
    auth_token = config_entry.data["auth_token"]

    # Coordinator'ın ilk verileri almasını bekle
    await coordinator.async_config_entry_first_refresh()

    thermostat = CosaThermostat(
        coordinator=coordinator,
        config_data={
            "device_id": device_id,
            "auth_token": auth_token,
        }
    )
    
    _LOGGER.debug("Adding Cosa Thermostat entity: %s", thermostat.unique_id)
    async_add_entities([thermostat], False)

class CosaThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a Cosa Thermostat device."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 0.1
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = ["home", "sleep", "away", "custom","auto","schedule"]
    _attr_translation_key = "preset_mode"
    _attr_min_temp = 5
    _attr_max_temp = 35
    _attr_target_temperature_step = 0.1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, coordinator: DataUpdateCoordinator, config_data: dict) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        
        self._device_id = config_data["device_id"]
        self._auth_token = config_data["auth_token"]
        
        # API'den gelen name değerini al
        device_name = None
        if self.coordinator.data:
            endpoint_data = self.coordinator.data.get("endpoint", {})
            device_name = endpoint_data.get("name")
        
        # Unique ID'yi ayarla
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}"
        
        # Name'i API'den gelen değer veya fallback olarak ayarla
        self._attr_name = device_name or f"Cosa Thermostat {self._device_id}"
        
        # Sıcaklık değerlerini saklamak için
        self._target_temperatures = {
            "home": None,
            "away": None,
            "sleep": None,
            "custom": None
        }
        self._attr_target_temperature = None
        self._attr_current_temperature = None
        self._attr_current_humidity = None
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.OFF
        self._attr_preset_mode = "home"
        self._attr_previous_preset_mode = "home"
        self._attr_previous_hvac_mode = HVACMode.OFF
        self._attr_previous_hvac_action = HVACAction.OFF
        # Sabitler
        self._VALID_OPTIONS = ["frozen", "home", "sleep", "away", "custom","auto","schedule"]
        self._VALID_MODES = ["manual", "auto", "schedule"]
        self._VALID_OPERATION_MODES = ["heating", "cooling", "remote"]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._attr_current_temperature

    @property
    def precision(self) -> float:
        """Return the precision of the temperature."""
        return self._attr_precision

    @property
    def current_humidity(self) -> float | None:
        """Return the current temperature."""
        return self._attr_current_humidity

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._attr_target_temperature

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return self._attr_hvac_mode

    @property
    def hvac_action(self) -> str:
        """Return the current running hvac operation."""
        return self._attr_hvac_action

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        return self._attr_preset_mode

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Coordinator update received: %s", self.coordinator.data)
        
        if not self.coordinator.data:
            _LOGGER.warning("No data received from coordinator")
            return

        try:
            endpoint = self.coordinator.data.get("endpoint", {})
            _LOGGER.debug("Processing endpoint data: %s", endpoint)
            
            if not endpoint:
                _LOGGER.warning("No endpoint data in coordinator update")
                return
            
            # Cihaz ismini güncelle
            if device_name := endpoint.get("name"):
                self._attr_name = device_name
            
            # Sıcaklık değerlerini güncelle
            self._target_temperatures = {
                "home": endpoint.get("homeTemperature"),
                "away": endpoint.get("awayTemperature"),
                "sleep": endpoint.get("sleepTemperature"),
                "custom": endpoint.get("customTemperature")
            }
            
            # Mevcut sıcaklık ve nem
            self._attr_current_temperature = endpoint.get("temperature")
            self._attr_current_humidity = endpoint.get("humidity")
            
            _LOGGER.debug(
                "Updated temperatures - Current: %s, Targets: %s",
                self._attr_current_temperature,
                self._target_temperatures
            )
            
            # Option ve mode bilgilerini güncelle
            current_option = endpoint.get("option")
            current_mode = endpoint.get("mode")
            
            _LOGGER.debug("Current option: %s, mode: %s", current_option, current_mode)
            
            if current_option == "frozen":
                self._attr_hvac_mode = HVACMode.OFF
                self._attr_hvac_action = HVACAction.OFF
            else:
                if current_mode == "auto":
                    self._attr_hvac_mode = HVACMode.HEAT
                    self._attr_preset_mode = "auto"
                elif current_mode == "manual":
                    self._attr_hvac_mode = HVACMode.HEAT
                    if current_option in self._attr_preset_modes:
                        self._attr_preset_mode = current_option
                elif current_mode == "schedule":
                    self._attr_hvac_mode = HVACMode.HEAT
                    self._attr_preset_mode = "schedule"

            
            
            # Previous option ve mode bilgilerini güncelle
            previous_option = endpoint.get("previousOption")
            previous_mode = endpoint.get("previousMode")
            if previous_option == "frozen":
                self._attr_previous_hvac_mode = HVACMode.OFF
                self._attr_previous_hvac_action = HVACAction.OFF
            else:
                if previous_mode == "auto":
                    self._attr_previous_hvac_mode = HVACMode.HEAT
                    self._attr_previous_preset_mode = "auto"
                elif previous_mode == "manual":
                    self._attr_previous_hvac_mode = HVACMode.HEAT
                    if previous_option in self._attr_preset_modes:
                        self._attr_previous_preset_mode = previous_option
                elif previous_mode == "schedule":
                    self._attr_previous_hvac_mode = HVACMode.HEAT
                    self._attr_previous_preset_mode = "schedule"

            # Kombi durumunu kontrol et
            combi_state = endpoint.get("combiState")
            operation_mode = endpoint.get("operationMode")
           
            
            # HVAC action güncelleme
            if self._attr_hvac_mode == HVACMode.OFF:
                self._attr_hvac_action = HVACAction.OFF
            elif operation_mode == "heating" and combi_state == "on":
                self._attr_hvac_action = HVACAction.HEATING
                _LOGGER.debug("Combi is actively heating")
            else:
                self._attr_hvac_action = HVACAction.IDLE
                _LOGGER.debug("Combi is idle")
            
            # Aktif modun hedef sıcaklığını ayarla
            if current_option in self._target_temperatures:
                self._attr_target_temperature = self._target_temperatures[current_option]
            
            _LOGGER.debug(
                "Updated state - Current Temp: %s, Target Temp: %s, Mode: %s, Action: %s, "
                "Combi State: %s, Operation Mode: %s, Option: %s",
                self._attr_current_temperature,
                self._attr_target_temperature,
                self._attr_hvac_mode,
                self._attr_hvac_action,
                combi_state,
                operation_mode,
                current_option
            )
            
        except Exception as ex:
            _LOGGER.exception("Error handling coordinator update: %s", ex)

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        # Önce mode'u manual'e çek
        await self._set_mode("manual")
        
        # Mevcut option için sıcaklığı güncelle
        current_option = self._attr_preset_mode
        if current_option not in self._target_temperatures:
            _LOGGER.error("Invalid preset mode for temperature update: %s", current_option)
            return
            
        # Tüm sıcaklıkları kopyala ve aktif modu güncelle
        new_temperatures = dict(self._target_temperatures)
        new_temperatures[current_option] = temperature
        
        session = async_get_clientsession(self.hass)
        headers = {"authToken": self._auth_token}
        data = {
            "endpoint": self._device_id,
            "targetTemperatures": new_temperatures
        }
        
        _LOGGER.debug("Setting temperature with data: %s", data)
        
        try:
            async with session.post(
                f"{API_BASE_URL}{API_SET_TARGET_TEMPERATURES}",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    # Yerel değerleri güncelle
                    self._target_temperatures = new_temperatures
                    self._attr_target_temperature = temperature
                    _LOGGER.debug("Temperature set successfully. Refreshing state...")
                    # API'nin güncellenmesi için kısa bir süre bekle
                    await asyncio.sleep(1)
                    # Veriyi güncelle
                    await self.coordinator.async_refresh()
                else:
                    response_text = await response.text()
                    _LOGGER.error(
                        "Failed to set temperature. Status: %s, Response: %s",
                        response.status,
                        response_text
                    )
        except Exception as ex:
            _LOGGER.error("Failed to set temperature: %s", ex)


    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self._attr_preset_modes:
            _LOGGER.error("Invalid preset mode: %s", preset_mode)
            return


        if(preset_mode == "auto"):
            await self._set_mode("auto")
        elif(preset_mode == "schedule"):
            await self._set_mode("schedule")
        else:
            # Önce mode'u manual'e çek
            await self._set_mode("manual")
            # Sonra option'ı ayarla
            session = async_get_clientsession(self.hass)
            headers = {"authToken": self._auth_token}
            data = {
                "endpoint": self._device_id,
                "option": preset_mode
            }
            
            try:
                async with session.post(
                    f"{API_BASE_URL}{API_SET_OPTION}",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 200:
                        self._attr_preset_mode = preset_mode
                        await self.coordinator.async_request_refresh()
                        _LOGGER.debug("Preset mode set to: %s", preset_mode)
            except Exception as ex:
                _LOGGER.error("Failed to set preset mode: %s", ex)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new hvac mode."""
        if hvac_mode == HVACMode.OFF:
            # Kombinin kapatılması için frozen option'ını kullan
            await self._set_option("frozen")
        else:
            # Isıtma modunu aç
            if(self._attr_previous_preset_mode == "auto"):
                await self._set_mode("auto")
            elif(self._attr_previous_preset_mode == "schedule"):
                await self._set_mode("schedule")
            else:
                await self._set_option(self._attr_previous_preset_mode)

        # API'nin güncellenmesi için kısa bir süre bekle
        await asyncio.sleep(1)
        # Veriyi güncelle
        await self.coordinator.async_refresh()

    async def _set_mode(self, mode: str) -> None:
        """Helper method to set the mode."""
        if mode not in self._VALID_MODES:
            return
            
        session = async_get_clientsession(self.hass)
        headers = {"authToken": self._auth_token}
        data = {
            "endpoint": self._device_id,
            "mode": mode
        }
        
        try:
            async with session.post(
                f"{API_BASE_URL}{API_SET_MODE}",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    _LOGGER.debug("Mode set to: %s", mode)
        except Exception as ex:
            _LOGGER.error("Failed to set mode: %s", ex) 

    
    async def _set_option(self, option: str) -> None:
        """Helper method to set the option."""
        if option not in self._VALID_OPTIONS:
            return
            
        session = async_get_clientsession(self.hass)
        headers = {"authToken": self._auth_token}
        data = {
            "endpoint": self._device_id,
            "option": option
        }
        
        try:
            async with session.post(
                f"{API_BASE_URL}{API_SET_OPTION}",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    _LOGGER.debug("Option set to: %s", option)
        except Exception as ex:
            _LOGGER.error("Failed to set option: %s", ex) 


   