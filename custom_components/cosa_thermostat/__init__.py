"""The Cosa Thermostat integration."""
from datetime import timedelta
import logging
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    API_BASE_URL,
    API_GET_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = ["climate", "sensor"]
UPDATE_INTERVAL = timedelta(seconds=10)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cosa Thermostat from a config entry."""
    device_id = entry.data["device_id"]
    auth_token = entry.data["auth_token"]

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            session = async_get_clientsession(hass)
            headers = {"authToken": auth_token}
            
            _LOGGER.debug("Fetching data for device %s", device_id)
            
            async with session.post(
                f"{API_BASE_URL}{API_GET_ENDPOINT}",
                headers=headers,
                json={"endpoint": device_id}
            ) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Error fetching data: %s, %s",
                        response.status,
                        await response.text()
                    )
                    raise UpdateFailed(f"Error communicating with API: {response.status}")
                
                data = await response.json()
                _LOGGER.debug("Received data: %s", data)
                return data
                
        except Exception as err:
            _LOGGER.exception("Error updating data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Cosa Thermostat {device_id}",
        update_method=async_update_data,
        update_interval=UPDATE_INTERVAL,
    )

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok 