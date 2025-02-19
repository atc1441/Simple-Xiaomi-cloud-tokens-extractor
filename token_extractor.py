import base64
import hashlib
import hmac
import json
import os
import re
import random
import time
from getpass import getpass
from sys import platform

import requests
from Crypto.Cipher import ARC4

if platform != "win32":
    import readline


class XiaomiCloudConnector:

    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._agent = self.generate_agent()
        self._device_id = self.generate_device_id()
        self._session = requests.session()
        self._sign = None
        self._ssecurity = None
        self.userId = None
        self._cUserId = None
        self._passToken = None
        self._location = None
        self._code = None
        self._serviceToken = None

    def login_step_1(self):
        url = "https://account.xiaomi.com/pass/serviceLogin?sid=xiaomiio&_json=true"
        headers = {
            "User-Agent": self._agent,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        cookies = {
            "userId": self._username
        }
        response = self._session.get(url, headers=headers, cookies=cookies)
        valid = response.status_code == 200 and "_sign" in self.to_json(response.text)
        if valid:
            self._sign = self.to_json(response.text)["_sign"]
        return valid

    def login_step_2(self):
        url = "https://account.xiaomi.com/pass/serviceLoginAuth2"
        headers = {
            "User-Agent": self._agent,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        fields = {
            "sid": "xiaomiio",
            "hash": hashlib.md5(str.encode(self._password)).hexdigest().upper(),
            "callback": "https://sts.api.io.mi.com/sts",
            "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
            "user": self._username,
            "_sign": self._sign,
            "_json": "true"
        }
        response = self._session.post(url, headers=headers, params=fields)
        valid = response is not None and response.status_code == 200
        if valid:
            json_resp = self.to_json(response.text)
            valid = "ssecurity" in json_resp and len(str(json_resp["ssecurity"])) > 4
            if valid:
                self._ssecurity = json_resp["ssecurity"]
                self.userId = json_resp["userId"]
                self._cUserId = json_resp["cUserId"]
                self._passToken = json_resp["passToken"]
                self._location = json_resp["location"]
                self._code = json_resp["code"]
            else:
                if "notificationUrl" in json_resp:
                    print("Two factor authentication required, please use following url and restart extractor:")
                    print(json_resp["notificationUrl"])
                    print()
        return valid

    def login_step_3(self):
        headers = {
            "User-Agent": self._agent,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = self._session.get(self._location, headers=headers)
        if response.status_code == 200:
            self._serviceToken = response.cookies.get("serviceToken")
        return response.status_code == 200

    def login(self):
        self._session.cookies.set("sdkVersion", "accountsdk-18.8.15", domain="mi.com")
        self._session.cookies.set("sdkVersion", "accountsdk-18.8.15", domain="xiaomi.com")
        self._session.cookies.set("deviceId", self._device_id, domain="mi.com")
        self._session.cookies.set("deviceId", self._device_id, domain="xiaomi.com")
        if self.login_step_1():
            if self.login_step_2():
                if self.login_step_3():
                    return True
                else:
                    print("Unable to get service token.")
            else:
                print("Invalid login or password.")
        else:
            print("Invalid username.")
        return False

    def get_homes(self, country):
        url = self.get_api_url(country) + "/v2/homeroom/gethome"
        params = {
            "data": '{"fg": true, "fetch_share": true, "fetch_share_dev": true, "limit": 300, "app_ver": 7}'}
        return self.execute_api_call_encrypted(url, params)

    def get_devices(self, country, home_id, owner_id):
        url = self.get_api_url(country) + "/v2/home/home_device_list"
        params = {
            "data": '{"home_owner": ' + str(owner_id) +
            ',"home_id": ' + str(home_id) +
            ',  "limit": 200,  "get_split_device": true, "support_smart_home": true}'
        }
        return self.execute_api_call_encrypted(url, params)

    def get_dev_cnt(self, country):
        url = self.get_api_url(country) + "/v2/user/get_device_cnt"
        params = {
            "data": '{ "fetch_own": true, "fetch_share": true}'
        }
        return self.execute_api_call_encrypted(url, params)

    def get_beaconkey(self, country, did):
        url = self.get_api_url(country) + "/v2/device/blt_get_beaconkey"
        params = {
            "data": '{"did":"' + did + '","pdid":1}'
        }
        return self.execute_api_call_encrypted(url, params)
    
    def get_devicefw(self, country, did):
        url = self.get_api_url(country) + "/v2/device/latest_ver"
        params = {
            "data": '{"did": "' + did + '"}'
        }
        return self.execute_api_call_encrypted(url, params)
    
    def download_firmware(self, url, name):
        folder_name = "firmwares"
        os.makedirs(folder_name, exist_ok=True)
        try:
            base_filename = url.split("?")[0].split("/")[-1]
            sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', "", name)
            file_name = f"{sanitized_name}_{base_filename}"
            file_path = os.path.join(folder_name, file_name)
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            return f"File downloaded successfully: {file_path}"
        except requests.exceptions.RequestException as e:
            return f"Failed to download the file: {e}"

    def execute_api_call_encrypted(self, url, params):
        headers = {
            "Accept-Encoding": "identity",
            "User-Agent": self._agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2",
            "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4",
        }
        cookies = {
            "userId": str(self.userId),
            "yetAnotherServiceToken": str(self._serviceToken),
            "serviceToken": str(self._serviceToken),
            "locale": "en_GB",
            "timezone": "GMT+02:00",
            "is_daylight": "1",
            "dst_offset": "3600000",
            "channel": "MI_APP_STORE"
        }
        millis = round(time.time() * 1000)
        nonce = self.generate_nonce(millis)
        signed_nonce = self.signed_nonce(nonce)
        fields = self.generate_enc_params(url, "POST", signed_nonce, nonce, params, self._ssecurity)
        response = self._session.post(url, headers=headers, cookies=cookies, params=fields)
        if response.status_code == 200:
            decoded = self.decrypt_rc4(self.signed_nonce(fields["_nonce"]), response.text)
            return json.loads(decoded)
        return None

    @staticmethod
    def get_api_url(country):
        return "https://" + ("" if country == "cn" else (country + ".")) + "api.io.mi.com/app"

    def signed_nonce(self, nonce):
        hash_object = hashlib.sha256(base64.b64decode(self._ssecurity) + base64.b64decode(nonce))
        return base64.b64encode(hash_object.digest()).decode('utf-8')

    @staticmethod
    def signed_nonce_sec(nonce, ssecurity):
        hash_object = hashlib.sha256(base64.b64decode(ssecurity) + base64.b64decode(nonce))
        return base64.b64encode(hash_object.digest()).decode('utf-8')

    @staticmethod
    def generate_nonce(millis):
        nonce_bytes = os.urandom(8) + (int(millis / 60000)).to_bytes(4, byteorder='big')
        return base64.b64encode(nonce_bytes).decode()

    @staticmethod
    def generate_agent():
        agent_id = "".join(map(lambda i: chr(i), [random.randint(65, 69) for _ in range(13)]))
        return f"Android-7.1.1-1.0.0-ONEPLUS A3010-136-{agent_id} APP/xiaomi.smarthome APPV/62830"

    @staticmethod
    def generate_device_id():
        return "".join(map(lambda i: chr(i), [random.randint(97, 122) for _ in range(6)]))

    @staticmethod
    def generate_signature(url, signed_nonce, nonce, params):
        signature_params = [url.split("com")[1], signed_nonce, nonce]
        for k, v in params.items():
            signature_params.append(f"{k}={v}")
        signature_string = "&".join(signature_params)
        signature = hmac.new(base64.b64decode(signed_nonce), msg=signature_string.encode(), digestmod=hashlib.sha256)
        return base64.b64encode(signature.digest()).decode()

    @staticmethod
    def generate_enc_signature(url, method, signed_nonce, params):
        signature_params = [str(method).upper(), url.split("com")[1].replace("/app/", "/")]
        for k, v in params.items():
            signature_params.append(f"{k}={v}")
        signature_params.append(signed_nonce)
        signature_string = "&".join(signature_params)
        return base64.b64encode(hashlib.sha1(signature_string.encode('utf-8')).digest()).decode()

    @staticmethod
    def generate_enc_params(url, method, signed_nonce, nonce, params, ssecurity):
        params['rc4_hash__'] = XiaomiCloudConnector.generate_enc_signature(url, method, signed_nonce, params)
        for k, v in params.items():
            params[k] = XiaomiCloudConnector.encrypt_rc4(signed_nonce, v)
        params.update({
            'signature': XiaomiCloudConnector.generate_enc_signature(url, method, signed_nonce, params),
            'ssecurity': ssecurity,
            '_nonce': nonce,
        })
        return params

    @staticmethod
    def to_json(response_text):
        return json.loads(response_text.replace("&&&START&&&", ""))

    @staticmethod
    def encrypt_rc4(password, payload):
        r = ARC4.new(base64.b64decode(password))
        r.encrypt(bytes(1024))
        return base64.b64encode(r.encrypt(payload.encode())).decode()

    @staticmethod
    def decrypt_rc4(password, payload):
        r = ARC4.new(base64.b64decode(password))
        r.encrypt(bytes(1024))
        return r.encrypt(base64.b64decode(payload))


def print_tabbed(value, tab):
    print(" " * tab + value)


def print_entry(key, value, tab):
    if value:
        print_tabbed(f'{key + ":": <10}{value}', tab)


def main():
    servers = ["cn", "de", "us", "ru", "tw", "sg", "in", "i2"]
    servers_str = ", ".join(servers)
    print("Username (email or user ID):")
    username = input()
    print("Password:")
    password = getpass("")
    print(f"Server (one of: {servers_str}) Leave empty to check all available:")
    server = input()
    while server not in ["", *servers]:
        print(f"Invalid server provided. Valid values: {servers_str}")
        print("Server:")
        server = input()

    print()
    if not server == "":
        servers = [server]

    connector = XiaomiCloudConnector(username, password)
    print("Logging in...")
    logged = connector.login()
    if logged:
        print("Logged in.")
        print()
        for current_server in servers:
            hh = []
            homes = connector.get_homes(current_server)
            if homes is not None:
                for h in homes['result']['homelist']:
                    hh.append({'home_id': h['id'], 'home_owner': connector.userId})
            dev_cnt = connector.get_dev_cnt(current_server)
            if dev_cnt is not None:
                for h in dev_cnt["result"]["share"]["share_family"]:
                    hh.append({'home_id': h['home_id'], 'home_owner': h['home_owner']})

            if len(hh) == 0:
                print(f'No homes found for server "{current_server}".')
                continue

            for home in hh:
                devices = connector.get_devices(current_server, home['home_id'], home['home_owner'])
                if devices is not None:
                    if devices["result"]["device_info"] is None or len(devices["result"]["device_info"]) == 0:
                        print(f'No devices found for server "{current_server}" @ home "{home["home_id"]}".')
                        continue
                    print(f'Devices found for server "{current_server}" @ home "{home["home_id"]}":')
                    for device in devices["result"]["device_info"]:
                        print_tabbed("---------", 3)
                        if "name" in device:
                            print_entry("NAME", device["name"], 3)
                        if "did" in device:
                            print_entry("ID", device["did"], 3)
                            if "blt" in device["did"]:
                                beaconkey = connector.get_beaconkey(current_server, device["did"])
                                if beaconkey and "result" in beaconkey and "beaconkey" in beaconkey["result"]:
                                    print_entry("BLE KEY", beaconkey["result"]["beaconkey"], 3)
                        if "mac" in device:
                            print_entry("MAC", device["mac"], 3)
                        if "localip" in device:
                            print_entry("IP", device["localip"], 3)
                        if "token" in device:
                            print_entry("TOKEN", device["token"], 3)
                        if "model" in device:
                            print_entry("MODEL", device["model"], 3)
                        if "did" in device:
                            model_name = "no_name_supplied"
                            if "model" in device and device["model"]:
                                model_name = device["model"]
                            firmwares = connector.get_devicefw(current_server, device["did"])
                            #print(firmwares)
                            if firmwares and "result" in firmwares and firmwares["result"] is not None:
                                if "url" in firmwares["result"] and firmwares["result"]["url"]:
                                    print_entry("Firmware", firmwares["result"]["url"], 3)
                                    print(connector.download_firmware(firmwares["result"]["url"], "url_" + model_name))
                                if "safe_url" in firmwares["result"] and firmwares["result"]["safe_url"]:
                                    print_entry("Firmware", firmwares["result"]["safe_url"], 3)
                                    print(connector.download_firmware(firmwares["result"]["safe_url"], "safe_url_" + model_name))
                                if "diff_url" in firmwares["result"] and firmwares["result"]["diff_url"]:
                                    print_entry("Firmware", firmwares["result"]["diff_url"], 3)
                                    print(connector.download_firmware(firmwares["result"]["diff_url"], "diff_url_" + model_name))
                                if "diff_safe_url" in firmwares["result"] and firmwares["result"]["diff_safe_url"]:
                                    print_entry("Firmware", firmwares["result"]["diff_safe_url"], 3)
                                    print(connector.download_firmware(firmwares["result"]["diff_safe_url"], "diff_safe_url_" + model_name))
                    print_tabbed("---------", 3)
                    print()
                else:
                    print(f"Unable to get devices from server {current_server}.")
    else:
        print("Unable to log in.")

    print()
    print("Press ENTER to finish")
    input()


if __name__ == "__main__":
    main()
