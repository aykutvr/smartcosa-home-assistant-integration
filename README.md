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

### Climate Entity

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

### Sensors

- Temperature sensor
- Humidity sensor
- Operation state sensor

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