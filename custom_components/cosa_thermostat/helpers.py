"""Shared helpers for the Cosa Thermostat integration."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_BASE_URL,
    AC_STATE_OFF,
    AC_STATE_DRY,
    AC_STATE_VENTILATION,
    AC_MODE_COOLING,
    AC_MODE_HEATING,
    AC_FAN_MODES,
)

_LOGGER = logging.getLogger(__name__)


def has_ac_support(endpoint: dict) -> bool:
    """Return True if the endpoint controls an air conditioner (IR remote)."""
    ac_settings = endpoint.get("acSettings") or {}
    return bool(
        ac_settings.get("acDeviceType")
        or ac_settings.get("remoteBrand")
        or endpoint.get("acState") is not None
    )


def parse_ac_state(raw: str | None) -> tuple[str, str | None, float | None] | None:
    """Parse an acState string into (mode, fan, temperature).

    Observed values: "off", "dry", "ventilation",
    "cooling_<fan>_<temp>" and "heating_<fan>_<temp>"
    where fan is one of auto/low/medium/high.
    Returns None for unknown/garbage values (the API echoes
    whatever string was last sent to sendIRCommand).
    """
    if not raw or raw == AC_STATE_OFF:
        return (AC_STATE_OFF, None, None)
    if raw == AC_STATE_DRY:
        return (AC_STATE_DRY, None, None)
    if raw == AC_STATE_VENTILATION:
        return (AC_STATE_VENTILATION, None, None)

    parts = raw.split("_")
    if len(parts) == 3 and parts[0] in (AC_MODE_COOLING, AC_MODE_HEATING) and parts[1] in AC_FAN_MODES:
        try:
            return (parts[0], parts[1], float(parts[2]))
        except ValueError:
            return None
    return None


async def async_api_post(hass: HomeAssistant, auth_token: str, path: str, data: dict) -> bool:
    """POST to the Cosa API, return True on HTTP 200."""
    session = async_get_clientsession(hass)
    headers = {"authToken": auth_token}
    try:
        async with session.post(
            f"{API_BASE_URL}{path}",
            headers=headers,
            json=data
        ) as response:
            if response.status == 200:
                return True
            _LOGGER.error(
                "API call %s failed. Status: %s, Response: %s",
                path,
                response.status,
                await response.text()
            )
    except Exception as ex:
        _LOGGER.error("API call %s failed: %s", path, ex)
    return False
