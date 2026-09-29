"""Support for Cosa Thermostat."""
from __future__ import annotations

import logging
import asyncio
from typing import Any
from datetime import timedelta

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
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
from homeassistant.exceptions import HomeAssistantError
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
    API_SEND_IR_COMMAND,
    API_SET_AC_SETTINGS,
    OPERATION_MODE_HEATING,
    OPERATION_MODE_COOLING,
    OPERATION_MODE_REMOTE,
    OPTION_FROZEN,
    AC_STATE_OFF,
    AC_STATE_DRY,
    AC_STATE_VENTILATION,
    AC_MODE_COOLING,
    AC_MODE_HEATING,
    AC_FAN_MODES,
    AC_MIN_TEMP,
    AC_MAX_TEMP,
    AC_DEFAULT_TARGET_TEMP,
    AC_PRESET_REMOTE,
    AC_PRESET_MODES,
    AC_THERMOSTAT_PRESETS,
    AC_SCHEDULING_PRESETS,
    AC_SETTINGS_READ_ONLY_KEYS,
    AC_THERMOSTAT_MIN_TEMP,
    AC_THERMOSTAT_MAX_TEMP,
    AC_THERMOSTAT_TEMP_STEP,
)
from .helpers import async_api_post, has_ac_support, parse_ac_state

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

    config_data = {
        "device_id": device_id,
        "auth_token": auth_token,
    }

    entities = [
        CosaThermostat(
            coordinator=coordinator,
            config_data=config_data,
        )
    ]

    # Klima (IR) destekli cihazlarda ayrı bir climate entity ekle
    endpoint = (coordinator.data or {}).get("endpoint", {})
    if has_ac_support(endpoint):
        _LOGGER.debug("Device has AC support, adding air conditioner entity")
        entities.append(
            CosaAirConditioner(
                coordinator=coordinator,
                config_data=config_data,
            )
        )

    _LOGGER.debug("Adding Cosa climate entities: %s", [e.unique_id for e in entities])
    async_add_entities(entities, False)

class CosaThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a Cosa Thermostat device."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 0.1
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = ["home", "sleep", "away", "custom","auto","schedule"]
    _attr_translation_key = "cosa_thermostat"
    _attr_min_temp = 5
    _attr_max_temp = 35
    _attr_target_temperature_step = 0.1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.PRESET_MODE |
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.TURN_OFF
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
            current_operation_mode = endpoint.get("operationMode")

            _LOGGER.debug(
                "Current option: %s, mode: %s, operationMode: %s",
                current_option, current_mode, current_operation_mode
            )

            # Cihaz kombi modunda değilse (örn. klima/IR kontrolündeyse) kombi kapalıdır
            if current_option == "frozen" or (
                current_operation_mode is not None
                and current_operation_mode != OPERATION_MODE_HEATING
            ):
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

    async def _ensure_heating_operation_mode(self) -> None:
        """Cihaz klima (remote) modundaysa kombi (heating) moduna geçir."""
        endpoint = (self.coordinator.data or {}).get("endpoint", {})
        operation_mode = endpoint.get("operationMode")
        # operationMode alanı olmayan (eski/kombi-only) cihazlara dokunma
        if operation_mode is not None and operation_mode != OPERATION_MODE_HEATING:
            await async_api_post(
                self.hass,
                self._auth_token,
                API_SET_OPERATION_MODE,
                {"endpoint": self._device_id, "operationMode": OPERATION_MODE_HEATING},
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        # Kombi kartıyla etkileşim kombi kontrolüne dönüş demektir
        await self._ensure_heating_operation_mode()

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

        # Kombi kartıyla etkileşim kombi kontrolüne dönüş demektir
        await self._ensure_heating_operation_mode()

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
            # Cihaz klima (remote) modundaysa önce kombi moduna geçir
            await self._ensure_heating_operation_mode()

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


class CosaAirConditioner(CoordinatorEntity, ClimateEntity):
    """Cosa'nın IR (kızılötesi) klima kontrolü.

    Cihaz klimayı sendIRCommand endpoint'i üzerinden yönetir; komutlar
    acState string'leri ile gönderilir: "cooling_<fan>_<temp>",
    "heating_<fan>_<temp>", "dry", "ventilation", "off".
    Klima kontrolü cihaz "remote" operationMode'undayken çalışır;
    kombi ısıtması ile karşılıklı dışlamalıdır (cihaz kendisi yönetir).
    """

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 1.0
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = AC_FAN_MODES
    _attr_preset_modes = AC_PRESET_MODES
    _attr_translation_key = "cosa_air_conditioner"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.PRESET_MODE |
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: DataUpdateCoordinator, config_data: dict) -> None:
        """Initialize the air conditioner."""
        super().__init__(coordinator)

        self._device_id = config_data["device_id"]
        self._auth_token = config_data["auth_token"]

        device_name = None
        if self.coordinator.data:
            endpoint_data = self.coordinator.data.get("endpoint", {})
            device_name = endpoint_data.get("name")

        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_ac"
        base_name = device_name or f"Cosa Thermostat {self._device_id}"
        self._attr_name = f"{base_name} AC"

        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.OFF
        self._attr_fan_mode = "auto"
        self._attr_target_temperature = None
        self._attr_current_temperature = None
        self._attr_current_humidity = None

        # Mod değiştirirken kullanılacak son bilinen fan/sıcaklık
        self._last_fan_mode = "auto"
        self._last_target_temp = AC_DEFAULT_TARGET_TEMP
        # Kapalıyken tekrar açmak için son aktif komut
        self._last_active_command: str | None = None

        # Preset durumu
        self._attr_preset_mode = AC_PRESET_REMOTE
        self._attr_previous_preset_mode = "home"
        # Preset başına hedef sıcaklıklar (kombi ile ORTAK)
        self._target_temperatures: dict[str, float | None] = {
            "home": None,
            "away": None,
            "sleep": None,
            "custom": None,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def _is_thermostat_mode(self) -> bool:
        """Termostatik (cooling) modda mı, kumanda (remote) modunda mı?"""
        return self._attr_preset_mode != AC_PRESET_REMOTE

    @property
    def min_temp(self) -> float:
        """Kumanda modunda IR aralığı, termostatik modda kombi aralığı."""
        return AC_THERMOSTAT_MIN_TEMP if self._is_thermostat_mode else AC_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Kumanda modunda IR aralığı, termostatik modda kombi aralığı."""
        return AC_THERMOSTAT_MAX_TEMP if self._is_thermostat_mode else AC_MAX_TEMP

    @property
    def target_temperature_step(self) -> float:
        """Kumanda modunda 1°, termostatik modda 0.1° (kombi ile aynı)."""
        return AC_THERMOSTAT_TEMP_STEP if self._is_thermostat_mode else 1

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            endpoint = (self.coordinator.data or {}).get("endpoint", {})
            if endpoint:
                self._process_endpoint_update(endpoint)
        except Exception as ex:
            _LOGGER.exception("Error handling AC coordinator update: %s", ex)

        # Her koşulda state'i yayınla; available/temperature/humidity
        # güncellemeleri parse edilemeyen acState'lerde bile işlensin
        self.async_write_ha_state()

    def _process_endpoint_update(self, endpoint: dict) -> None:
        """Update entity attributes from endpoint data."""
        if device_name := endpoint.get("name"):
            self._attr_name = f"{device_name} AC"

        self._attr_current_temperature = endpoint.get("temperature")
        self._attr_current_humidity = endpoint.get("humidity")

        # Preset sıcaklıkları kombi ile ortaktır
        self._target_temperatures = {
            "home": endpoint.get("homeTemperature"),
            "away": endpoint.get("awayTemperature"),
            "sleep": endpoint.get("sleepTemperature"),
            "custom": endpoint.get("customTemperature"),
        }

        operation_mode = endpoint.get("operationMode")
        raw_ac_state = endpoint.get("acState")

        _LOGGER.debug(
            "AC update - operationMode: %s, acState: %s, option: %s, mode: %s",
            operation_mode, raw_ac_state, endpoint.get("option"), endpoint.get("mode")
        )

        if operation_mode == OPERATION_MODE_HEATING:
            # Cihaz kombi kontrolünde; klima kapalı
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
        elif operation_mode == OPERATION_MODE_COOLING:
            self._process_thermostat_update(endpoint, raw_ac_state)
        else:
            # remote (veya operationMode alanı olmayan cihaz)
            self._process_remote_update(raw_ac_state)

    def _process_thermostat_update(self, endpoint: dict, raw_ac_state: str | None) -> None:
        """Termostatik klima modu: cihaz klimayı oda sıcaklığına göre yönetir."""
        option = endpoint.get("option")
        mode = endpoint.get("mode")

        # Preset: kombi entity'sindeki mantığın aynısı
        if mode in AC_SCHEDULING_PRESETS:
            self._attr_preset_mode = mode
        elif option in AC_THERMOSTAT_PRESETS:
            self._attr_preset_mode = option
            self._attr_previous_preset_mode = option
        elif self._attr_preset_mode == AC_PRESET_REMOTE:
            # option "frozen" (klima kapalı) ve elimizde bir preset yok — örn. HA
            # yeniden başladı. Cihaz termostatik modda olduğu için kumanda
            # preset'inde kalmak yanlıştır: cihazın previousOption'ına, o da
            # yoksa bilinen son preset'e dön. (Kombi entity'si de previousOption
            # okuyarak aynı sorunu çözüyor.) previous_preset_mode'u da aynı
            # değere çekiyoruz ki COOL'a dönüldüğünde (async_set_hvac_mode)
            # gerçekten bu preset'e restore edilsin.
            previous_option = endpoint.get("previousOption")
            restored_preset = (
                previous_option
                if previous_option in AC_THERMOSTAT_PRESETS
                else self._attr_previous_preset_mode
            )
            self._attr_preset_mode = restored_preset
            self._attr_previous_preset_mode = restored_preset

        if option == OPTION_FROZEN:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
        else:
            self._attr_hvac_mode = HVACMode.COOL
            # Kumanda modunun aksine burada GERÇEK geri bildirim var:
            # cihaz klimayı çalıştırdıysa acState "off" değildir
            parsed = parse_ac_state(raw_ac_state)
            running = parsed is not None and parsed[0] != AC_STATE_OFF
            self._attr_hvac_action = HVACAction.COOLING if running else HVACAction.IDLE

        if option in self._target_temperatures:
            self._attr_target_temperature = self._target_temperatures[option]

        # Fan hızı termostatik modda acSettings'ten gelir
        ac_settings = endpoint.get("acSettings") or {}
        fan_speed = ac_settings.get("fanSpeed")
        if fan_speed in AC_FAN_MODES:
            self._attr_fan_mode = fan_speed

    def _process_remote_update(self, raw_ac_state: str | None) -> None:
        """Kumanda modu: acState doğrudan klimanın durumudur."""
        self._attr_preset_mode = AC_PRESET_REMOTE

        parsed = parse_ac_state(raw_ac_state)
        if parsed is None:
            # API son gönderilen string'i echo'lar; tanınmayan değerlerde
            # (örn. eşleşmeyen ham komutlar) mod/fan/hedef durumunu koru
            return

        ac_mode, fan, temp = parsed

        if ac_mode == AC_STATE_OFF:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
        elif ac_mode == AC_MODE_COOLING:
            self._attr_hvac_mode = HVACMode.COOL
            self._attr_hvac_action = HVACAction.COOLING
            self._attr_fan_mode = fan
            self._attr_target_temperature = temp
            self._last_fan_mode = fan
            self._last_target_temp = temp
            self._last_active_command = raw_ac_state
        elif ac_mode == AC_MODE_HEATING:
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_hvac_action = HVACAction.HEATING
            self._attr_fan_mode = fan
            self._attr_target_temperature = temp
            self._last_fan_mode = fan
            self._last_target_temp = temp
            self._last_active_command = raw_ac_state
        elif ac_mode == AC_STATE_DRY:
            self._attr_hvac_mode = HVACMode.DRY
            self._attr_hvac_action = HVACAction.DRYING
            self._last_active_command = raw_ac_state
        elif ac_mode == AC_STATE_VENTILATION:
            self._attr_hvac_mode = HVACMode.FAN_ONLY
            self._attr_hvac_action = HVACAction.FAN
            self._last_active_command = raw_ac_state

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _build_command(self, ac_mode: str, fan: str | None = None, temp: float | None = None) -> str:
        """Build an acState command string."""
        fan = fan or self._last_fan_mode or "auto"
        temp = temp if temp is not None else self._last_target_temp
        temp = int(round(max(AC_MIN_TEMP, min(AC_MAX_TEMP, temp))))
        return f"{ac_mode}_{fan}_{temp}"

    async def _send_ir_command(self, command: str) -> None:
        """Send an IR command (acState string) to the AC."""
        _LOGGER.debug("Sending IR command: %s", command)
        success = await async_api_post(
            self.hass,
            self._auth_token,
            API_SEND_IR_COMMAND,
            {"endpoint": self._device_id, "command": command},
        )
        if not success:
            raise HomeAssistantError(f"Failed to send AC command: {command}")

    async def _set_operation_mode(self, operation_mode: str) -> None:
        """Cihazın çalışma modunu ayarla (cooling | remote).

        setOperationMode idempotenttir; coordinator verisi 10 sn'ye kadar
        bayat olabileceğinden koşulsuz gönderilir. operationMode alanı
        olmayan (eski) cihazlara dokunulmaz.
        """
        endpoint = (self.coordinator.data or {}).get("endpoint", {})
        if endpoint.get("operationMode") is None:
            return
        await async_api_post(
            self.hass,
            self._auth_token,
            API_SET_OPERATION_MODE,
            {"endpoint": self._device_id, "operationMode": operation_mode},
        )

    async def _ensure_remote_mode(self) -> None:
        """Cihazı kumanda (IR) moduna geçir."""
        await self._set_operation_mode(OPERATION_MODE_REMOTE)

    async def _ensure_cooling_mode(self) -> None:
        """Cihazı termostatik klima (cooling) moduna geçir."""
        await self._set_operation_mode(OPERATION_MODE_COOLING)

    async def _set_mode(self, mode: str) -> None:
        """Zamanlama modunu ayarla: manual | auto | schedule."""
        await async_api_post(
            self.hass,
            self._auth_token,
            API_SET_MODE,
            {"endpoint": self._device_id, "mode": mode},
        )

    async def _set_option(self, option: str) -> None:
        """Konfor seçeneğini ayarla: home | away | sleep | custom | frozen."""
        await async_api_post(
            self.hass,
            self._auth_token,
            API_SET_OPTION,
            {"endpoint": self._device_id, "option": option},
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode.

        "remote" kumanda (IR passthrough) modudur; diğerleri cihazın
        termostatik klima kontrolünü açar.
        """
        if preset_mode not in AC_PRESET_MODES:
            _LOGGER.error("Invalid AC preset mode: %s", preset_mode)
            return

        # Termostatik presetler operationMode alanı gerektirir; bu alanı
        # olmayan (eski/kumanda-only) cihazlarda anlamsızdır ve cihazı
        # honor edemeyeceği bir duruma sürüklerdi
        if preset_mode != AC_PRESET_REMOTE:
            endpoint = (self.coordinator.data or {}).get("endpoint", {})
            if endpoint.get("operationMode") is None:
                _LOGGER.error(
                    "Cannot set thermostatic preset %s: device has no operationMode field",
                    preset_mode,
                )
                return

        if preset_mode == AC_PRESET_REMOTE:
            await self._ensure_remote_mode()
        else:
            await self._ensure_cooling_mode()
            if preset_mode in AC_SCHEDULING_PRESETS:
                await self._set_mode(preset_mode)
            else:
                await self._set_mode("manual")
                await self._set_option(preset_mode)
                self._attr_previous_preset_mode = preset_mode

        self._attr_preset_mode = preset_mode
        await self._refresh_state()

    async def _refresh_state(self) -> None:
        """Give the API a moment to settle, then refresh."""
        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new hvac mode."""
        if self._is_thermostat_mode:
            if hvac_mode == HVACMode.OFF:
                endpoint = (self.coordinator.data or {}).get("endpoint", {})
                device_cooling = endpoint.get("operationMode") == OPERATION_MODE_COOLING
                if not device_cooling:
                    # Cihaz termostatik klima kontrolünde değil (örn. kombi
                    # çalışıyor): klima zaten kapalı. Burada frozen göndermek
                    # kombiyi kapatırdı — option/mode alanları ortaktır.
                    _LOGGER.debug(
                        "AC already off (operationMode is not cooling); skipping"
                    )
                    return
                # Termostatik modda kapatma = frozen option (IR değil)
                await self._set_option(OPTION_FROZEN)
                await self._refresh_state()
                return
            if hvac_mode == HVACMode.COOL:
                # option/mode alanları ortak olduğu için, bunları yazmadan
                # önce cihazı koşulsuz olarak termostatik klima (cooling)
                # moduna geçiriyoruz; aksi halde buradaki setMode/setOption
                # kombiyi sürükleyebilir. setOperationMode idempotenttir ve
                # coordinator verisi 10 sn'ye kadar bayat olabileceğinden,
                # olası bayat veriye bakarak bu çağrıyı atlamıyoruz.
                await self._ensure_cooling_mode()
                preset = self._attr_previous_preset_mode
                if preset not in AC_THERMOSTAT_PRESETS:
                    preset = "home"
                await self._set_mode("manual")
                await self._set_option(preset)
                self._attr_preset_mode = preset
                await self._refresh_state()
                return
            # DRY / FAN_ONLY / HEAT termostatik modda yoktur; kumandaya geç
            # ve komutu orada uygula (gizlemek yerine affedici davranış)
            await self.async_set_preset_mode(AC_PRESET_REMOTE)

        if hvac_mode == HVACMode.OFF:
            await self._send_ir_command(AC_STATE_OFF)
        else:
            await self._ensure_remote_mode()
            if hvac_mode == HVACMode.DRY:
                command = AC_STATE_DRY
            elif hvac_mode == HVACMode.FAN_ONLY:
                command = AC_STATE_VENTILATION
            elif hvac_mode == HVACMode.COOL:
                command = self._build_command(AC_MODE_COOLING)
            elif hvac_mode == HVACMode.HEAT:
                command = self._build_command(AC_MODE_HEATING)
            else:
                _LOGGER.error("Unsupported AC hvac mode: %s", hvac_mode)
                return
            await self._send_ir_command(command)

        await self._refresh_state()

    async def async_turn_on(self) -> None:
        """Turn the AC on, restoring the last active state if known."""
        if self._is_thermostat_mode:
            # Termostatik modda "son aktif komut" bir IR string'idir ve
            # cihazın kendi kendine soğutmasıyla ilgisizdir; COOL moduna
            # geçmek preset'i (ve dolayısıyla cihazı) yeniden başlatır
            await self.async_set_hvac_mode(HVACMode.COOL)
            return

        await self._ensure_remote_mode()
        command = self._last_active_command or self._build_command(AC_MODE_COOLING)
        await self._send_ir_command(command)
        await self._refresh_state()

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        # climate.set_temperature isteğe bağlı hvac_mode ile gelebilir;
        # önce moda geç (komut saklanan yeni sıcaklıkla kurulur)
        requested_mode = kwargs.get(ATTR_HVAC_MODE)
        if requested_mode is not None and requested_mode != self._attr_hvac_mode:
            self._last_target_temp = temperature
            await self.async_set_hvac_mode(requested_mode)
            if self._is_thermostat_mode:
                # Termostatik modda mod geçişi sıcaklığı yazmaz (setMode/
                # setOption sıcaklık alanı içermez); burada gönderilmezse
                # istenen sıcaklık sessizce kaybolur.
                await self._async_set_thermostat_temperature(temperature)
            return

        if self._is_thermostat_mode:
            await self._async_set_thermostat_temperature(temperature)
            return

        self._last_target_temp = temperature

        if self._attr_hvac_mode == HVACMode.COOL:
            await self._send_ir_command(self._build_command(AC_MODE_COOLING, temp=temperature))
            await self._refresh_state()
        elif self._attr_hvac_mode == HVACMode.HEAT:
            await self._send_ir_command(self._build_command(AC_MODE_HEATING, temp=temperature))
            await self._refresh_state()
        else:
            # dry/fan/off modlarında sıcaklık uygulanmaz; sonraki
            # cool/heat geçişinde kullanılmak üzere saklanır
            self._attr_target_temperature = temperature
            self.async_write_ha_state()

    async def _async_set_thermostat_temperature(self, temperature: float) -> None:
        """Termostatik modda aktif preset'in hedef sıcaklığını yaz.

        DİKKAT: preset sıcaklıkları kombi ile ORTAKTIR. Buradan yapılan
        değişiklik kombinin aynı preset hedefini de değiştirir; Cosa'nın
        kendi uygulaması da böyle davranır (ayrı bir soğutma hedefi yoktur).
        """
        preset = self._attr_preset_mode
        if preset not in self._target_temperatures:
            # auto/schedule preset'lerinde cihazın seçtiği aktif option kullanılır
            endpoint = (self.coordinator.data or {}).get("endpoint", {})
            preset = endpoint.get("option")
        if preset not in self._target_temperatures:
            _LOGGER.error(
                "Cannot set AC temperature for preset %s (active option: %s)",
                self._attr_preset_mode, preset
            )
            return

        new_temperatures = {
            k: v for k, v in self._target_temperatures.items() if v is not None
        }
        new_temperatures[preset] = temperature

        success = await async_api_post(
            self.hass,
            self._auth_token,
            API_SET_TARGET_TEMPERATURES,
            {"endpoint": self._device_id, "targetTemperatures": new_temperatures},
        )
        if not success:
            raise HomeAssistantError(f"Failed to set AC target temperature: {temperature}")

        self._target_temperatures[preset] = temperature
        self._attr_target_temperature = temperature
        await self._refresh_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode not in AC_FAN_MODES:
            _LOGGER.error("Invalid fan mode: %s", fan_mode)
            return

        if self._is_thermostat_mode:
            await self._async_set_thermostat_fan_speed(fan_mode)
            return

        self._last_fan_mode = fan_mode

        if self._attr_hvac_mode == HVACMode.COOL:
            await self._send_ir_command(self._build_command(AC_MODE_COOLING, fan=fan_mode))
            await self._refresh_state()
        elif self._attr_hvac_mode == HVACMode.HEAT:
            await self._send_ir_command(self._build_command(AC_MODE_HEATING, fan=fan_mode))
            await self._refresh_state()
        else:
            # dry/fan/off modlarında fan hızı ayrı gönderilemez; saklanır
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    async def _async_set_thermostat_fan_speed(self, fan_mode: str) -> None:
        """Termostatik modda cihazın kullandığı fan hızını acSettings'e yaz.

        setACSettings tam nesne bekler (eksik alan -> code 157) ve hiçbir
        doğrulama yapmaz; fan_mode çağrılmadan önce allowlist'ten geçmiştir.
        """
        endpoint = (self.coordinator.data or {}).get("endpoint", {})
        ac_settings = endpoint.get("acSettings")
        if not ac_settings:
            _LOGGER.error("Cannot set AC fan speed: acSettings unavailable")
            return

        payload = {
            k: v for k, v in ac_settings.items()
            if k not in AC_SETTINGS_READ_ONLY_KEYS
        }
        payload["fanSpeed"] = fan_mode

        success = await async_api_post(
            self.hass,
            self._auth_token,
            API_SET_AC_SETTINGS,
            {"endpoint": self._device_id, "acSettings": payload},
        )
        if not success:
            raise HomeAssistantError(f"Failed to set AC fan speed: {fan_mode}")

        self._attr_fan_mode = fan_mode
        await self._refresh_state()
