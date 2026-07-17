# Cosa Thermostat Integration for Home Assistant

This is a custom integration for Home Assistant that allows you to control your Cosa Thermostat. The integration provides both climate control and sensor capabilities.

## Features

- Control your Cosa Thermostat through Home Assistant
- Monitor current temperature and humidity
- Set target temperatures for different modes (home, away, sleep, custom)
- Support for multiple operation modes:
  - Manual mode
  - Auto mode
  - Schedule mode
- Real-time status updates
- Supports both heating control and monitoring
- **Air conditioner (AC) control** on AC-capable Cosa devices (models with
  "AC" in the product code, e.g. P4TR-21-AC): a separate climate entity with
  cool / heat / dry / fan-only modes and fan speed control, using the
  thermostat's built-in IR remote capability

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add the URL of this repository
6. Select "Integration" as the category
7. Click "Add"
8. Find "Cosa Thermostat" in the integration list and click "Download"
9. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/cosa_thermostat` folder to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to Home Assistant Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Cosa Thermostat"
4. Follow the configuration steps:
   - Enter your Email Address
   - Enter your Password
   - Choose your home endpoint

## Supported Features

### Climate Entity (Combi / Boiler)

- Current temperature display
- Current humidity display
- Target temperature control
- Operation modes:
  - Heat
  - Off
- Preset modes:
  - Home
  - Away
  - Sleep
  - Custom
  - Auto
  - Schedule

### Climate Entity (Air Conditioner)

Created automatically for AC-capable devices (the Cosa app must be paired
with your AC via Settings > AC Settings first):

- HVAC modes: Cool, Heat, Dry, Fan only, Off
- Fan speeds: Auto, Low, Medium, High
- Target temperature control (16–30 °C)
- Switching the AC on automatically takes the device out of combi mode
  (and vice versa) — the device enforces this itself

#### Preset modes (AC)

- **Remote** — Cosa acts as a plain IR remote: you pick the mode, fan speed
  and temperature, and the command is sent straight to the AC. This is the
  only mode that offers dry and fan-only.
- **Home / Away / Sleep / Custom / Auto Control / Weekly Schedule** — the
  thermostat drives the AC itself, switching it on and off to reach the
  preset's target temperature, exactly like it does with the combi. In these
  presets the AC state reported by Home Assistant reflects whether the device
  is actually cooling.

> **The preset temperatures are shared with the combi.** Cosa stores one target
> temperature per preset (home/away/sleep/custom) and uses it for whichever
> system is active. Changing the AC's Home target to 24 °C also changes the
> combi's Home target to 24 °C — there are no separate cooling setpoints. The
> Cosa app behaves the same way.

#### Known limitations

- **No swing (louver) control.** The Cosa cloud API exposes no command for it
  and the Cosa app has no swing button either, even though the IR profile
  contains a `SWING` key. This is a limitation of Cosa, not of this
  integration.
- **The AC beeps twice on some changes.** When the fan speed is anything other
  than "auto", the thermostat has to send a second IR key for the fan, so the
  AC beeps twice. The Cosa app does exactly the same — it is device behaviour,
  not a bug.

Note: IR control is one-way (like a remote), so the state shown reflects
the last command sent through Cosa, not changes made with the AC's own
remote control.

If you pair your AC in the Cosa app *after* adding this integration,
reload the integration (Settings > Devices & Services > Cosa Thermostat >
Reload) for the AC entity to appear.

### Sensors

- Temperature sensor
- Humidity sensor
- Operation state sensor
- AC state sensor (AC-capable devices)

## Contributing

Feel free to contribute to this project by:
- Reporting issues
- Suggesting new features
- Creating pull requests

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is not officially associated with Cosa. Use at your own risk.

## Documentation

For more information, please visit the GitHub repository: [https://github.com/aykutvr/smartcosa-home-assistant-integration](https://github.com/aykutvr/smartcosa-home-assistant-integration) 