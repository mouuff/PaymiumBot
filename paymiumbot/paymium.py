
import webbrowser
import requests
import json
import sys
import os
import urllib3
import time

from .constants import Constants
from .helper import get_script_path

urllib3.disable_warnings()

token_path = get_script_path("paymium_token.json")


def _assert_headers_ok(resp):
    if not resp.headers["Status"].startswith("2"):
        raise AssertionError('Status != 2xx: ' + str(resp.headers))


def _write_token(token):
    with open(token_path, 'w') as f:
        json.dump(token, f)


def _read_token():
    if not os.path.isfile(token_path):
        return None
    with open(token_path, 'r') as f:
        token = json.load(f)
    expires_at = token["created_at"] + token["expires_in"] - 30
    now = int(time.time())
    if expires_at <= now:
        print("Token expired: " + str(expires_at) + " >= " + str(now))
        return None
    return token


class Paymium:
    def __init__(self, client_id, client_secret, use_saved_token=True):
        self._token = None
        if use_saved_token:
            self._token = _read_token()
        self.client_id = client_id
        self.client_secret = client_secret

    def _set_token(self, token):
        assert token != None
        self._token = token
        _write_token(token)

    @property
    def token(self):
        if not self._token:
            return self._token
        return self._token.copy()

    @property
    def _bearer_headers(self):
        return {"Authorization": "Bearer " + self.token["access_token"]}

    def post_auth(self, url, data):
        resp = requests.post(url, data=data, verify=False,
                             allow_redirects=False, auth=(self.client_id, self.client_secret))
        _assert_headers_ok(resp)
        return resp

    def post(self, path, data):
        resp = requests.post(Constants.URL_API + path, data=data, headers=self._bearer_headers, verify=False,
                             allow_redirects=False)
        _assert_headers_ok(resp)

    def public_get(self, path, data):
        resp = requests.get(
            Constants.URL_API + path, data=data, verify=False)
        _assert_headers_ok(resp)
        return json.loads(resp.text)

    def get(self, path):
        resp = requests.get(
            Constants.URL_API + path, verify=False, headers=self._bearer_headers)
        _assert_headers_ok(resp)
        return json.loads(resp.text)

    def new_token(self, code):
        data = {
            "grant_type": 'authorization_code',
            "redirect_uri": Constants.URL_REDIRECT,
            "code": code
        }
        access_token_response = self.post_auth(Constants.URL_TOKEN, data)
        self._set_token(json.loads(access_token_response.text))

    def refresh_token(self):
        data = {
            "grant_type": 'refresh_token',
            "redirect_uri": Constants.URL_REDIRECT,
            "refresh_token": self.token["refresh_token"]
        }
        refresh_token_response = self.post_auth(Constants.URL_TOKEN, data)
        self._set_token(json.loads(refresh_token_response.text))

    def user_auth(self):
        if self.token:
            print("Using saved token")
            return
        url = "https://www.paymium.com/api/oauth/authorize?client_id=" + self.client_id + \
            "&redirect_uri=https%3A%2F%2Fwww.paymium.com%2Fpage%2Foauth%2Ftest&response_type=code&scope=basic+activity+trade"
        try:
            webbrowser.open_new_tab(url)
        except webbrowser.Error:
            print("Open this url:")
            print(url)
        code = input('Enter code: ')
        self.new_token(code)
        print("Auth successful")

    def get_trades(self, since=None):
        data = {}
        if since:
            data["since"] = int(since)
        return self.public_get("/api/v1/data/eur/trades", data=data)

    def get_ticker(self):
        return self.public_get("/api/v1/data/eur/ticker", {})

    def get_user(self):
        return self.get("/api/v1/user")

    def post_order(self, data):
        return self.post("/api/v1/user/orders", data=data)

    def post_limit_order(self, direction, price, amount):
        data = {
            "type": "LimitOrder",
            "currency": "EUR",
            "direction": direction,
            "price": price,
            "amount": amount,
        }
        return self.post_order(data)

    def buy_at(self, price, btc_amount):
        return self.post_limit_order("buy", price, btc_amount)

    def sell_at(self, price, btc_amount):
        return self.post_limit_order("sell", price, btc_amount)
