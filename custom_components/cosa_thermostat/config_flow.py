"""Config flow for Cosa Thermostat integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, API_BASE_URL, API_LOGIN, API_GET_ENDPOINTS

_LOGGER = logging.getLogger(__name__)

class CosaThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cosa Thermostat."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._auth_token = None
        self._email = None
        self._password = None
        self._devices = None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                self._email = user_input[CONF_EMAIL]
                self._password = user_input[CONF_PASSWORD]
                self._auth_token = await self._validate_login(self._email, self._password)
                self._devices = await self._get_devices()
                
                # Eğer cihaz varsa, cihaz seçme adımına geç
                if self._devices:
                    return await self.async_step_select_device()
                else:
                    errors["base"] = "no_devices"
                    
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle device selection."""
        errors = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device = next((d for d in self._devices if d["id"] == device_id), None)
            
            if device:
                return self.async_create_entry(
                    title=f"Cosa Thermostat - {device.get('name', device_id)}",
                    data={
                        CONF_EMAIL: self._email,
                        CONF_PASSWORD: self._password,
                        CONF_DEVICE_ID: device_id,
                        "device_name": device.get("name", ""),
                        "auth_token": self._auth_token
                    },
                )

        # Cihaz listesini oluştur
        devices = {
            device["id"]: f"{device.get('name', '')} ({device['id']})"
            for device in self._devices
        }

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ID): vol.In(devices)
            }),
            errors=errors,
        )

    async def _validate_login(self, email: str, password: str) -> str:
        """Validate login credentials and return auth token."""
        session = async_get_clientsession(self.hass)
        
        try:
            async with session.post(
                f"{API_BASE_URL}{API_LOGIN}",
                json={"email": email, "password": password}
            ) as response:
                if response.status != 200:
                    raise InvalidAuth
                
                response_data = await response.json()
                if "authToken" not in response_data:
                    raise InvalidAuth
                
                return response_data["authToken"]
                
        except aiohttp.ClientError as ex:
            raise CannotConnect from ex

    async def _get_devices(self) -> list:
        """Get list of devices."""
        session = async_get_clientsession(self.hass)
        headers = {"authToken": self._auth_token}
        
        try:
            async with session.get(
                f"{API_BASE_URL}{API_GET_ENDPOINTS}",
                headers=headers
            ) as response:
                if response.status != 200:
                    raise CannotConnect
                
                response_data = await response.json()
                return response_data.get("endpoints", [])
                
        except aiohttp.ClientError as ex:
            raise CannotConnect from ex

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth.""" 