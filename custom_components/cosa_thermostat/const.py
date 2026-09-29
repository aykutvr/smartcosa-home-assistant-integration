"""Constants for the Cosa Thermostat integration."""
from homeassistant.const import Platform

DOMAIN = "cosa_thermostat"
PLATFORMS = [Platform.CLIMATE]

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
API_SEND_IR_COMMAND = "/api/endpoints/sendIRCommand"

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

# Device operation modes (endpoint.operationMode)
OPERATION_MODE_HEATING = "heating"
OPERATION_MODE_COOLING = "cooling"
OPERATION_MODE_REMOTE = "remote"

# AC state strings (endpoint.acState / sendIRCommand payloads)
# Composite states: "<mode>_<fanSpeed>_<targetTemp>" e.g. "cooling_high_21"
AC_STATE_OFF = "off"
AC_STATE_DRY = "dry"
AC_STATE_VENTILATION = "ventilation"
AC_MODE_COOLING = "cooling"
AC_MODE_HEATING = "heating"
AC_FAN_MODES = ["auto", "low", "medium", "high"]

# AC temperature limits (standard IR remote range)
AC_MIN_TEMP = 16
AC_MAX_TEMP = 30
AC_DEFAULT_TARGET_TEMP = 24

API_SET_AC_SETTINGS = "/api/endpoints/setACSettings"

# AC preset modes (klima entity'si)
# "remote" = Kumanda: IR passthrough (operationMode=remote)
# diğerleri = termostatik klima kontrolü (operationMode=cooling)
AC_PRESET_REMOTE = "remote"
AC_THERMOSTAT_PRESETS = ["home", "away", "sleep", "custom"]
AC_SCHEDULING_PRESETS = ["auto", "schedule"]
AC_PRESET_MODES = [AC_PRESET_REMOTE] + AC_THERMOSTAT_PRESETS + AC_SCHEDULING_PRESETS

# setACSettings'e geri yazılmayacak salt-okunur alanlar
AC_SETTINGS_READ_ONLY_KEYS = ("keys", "acInfo", "acDeviceType")

# Termostatik moddaki hedef sıcaklık aralığı (kombi ile ORTAK alanlar)
AC_THERMOSTAT_MIN_TEMP = 5
AC_THERMOSTAT_MAX_TEMP = 35
AC_THERMOSTAT_TEMP_STEP = 0.1
