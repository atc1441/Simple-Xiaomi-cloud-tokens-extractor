
# Xiaomi Cloud Tokens Extractor

### This is a fork from the original Repo, all credit belongs to it: https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor

This tool/script retrieves tokens for all devices connected to Xiaomi cloud and encryption keys for BLE devices.

You will need to provide Xiaomi Home credentials (_not ones from Roborock app_):
- username (e-mail or Xiaomi Cloud account ID)
- password
- Xiaomi's server region (`cn` - China, `de` - Germany etc.). Leave empty to check all available

In return all of your devices connected to account will be listed, together with their name and IP address.

# Additional functions to the original version

This variant is intendet to be simply used with Python without docker etc.

It allows to also get the latest Firmware version URL from the devices in your Account.

- The firmware URL will be logged in the device infos
- All firmware files will be downloaded to the folder firmwares

