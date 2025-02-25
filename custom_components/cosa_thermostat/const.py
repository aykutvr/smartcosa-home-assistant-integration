"""Constants for the Cosa Thermostat integration."""
from homeassistant.const import Platform

DOMAIN = "cosa_thermostat"
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

# Configuration
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"

# API Constants
API_BASE_URL = "https://kiwi.cosa.com.tr"
API_LOGIN = "/api/users/login"
API_GET_ENDPOINTS = "/api/endpoints/getEndpoints/"
API_GET_ENDPOINT = "/api/endpoints/getEndpoint"
API_GET_TELEMETRIES = "/api/endpoints/getTelemetries"
API_SET_TARGET_TEMPERATURES = "/api/endpoints/setTargetTemperatures"
API_SET_MODE = "/api/endpoints/setMode"
API_SET_OPTION = "/api/endpoints/setOption"
API_SET_OPERATION_MODE = "/api/endpoints/setOperationMode"

# Operation Modes
MODE_AUTO = "auto"
MODE_MANUAL = "manual"
MODE_SCHEDULE = "schedule"

# Options
OPTION_FROZEN = "frozen"
OPTION_HOME = "home"
OPTION_AWAY = "away"
OPTION_SLEEP = "sleep"
OPTION_CUSTOM = "custom" 
OPTION_AUTO = "auto"
OPTION_SCHEDULE = "schedule"
