import base64
import json

import pytest
import requests

from uac_desktop import cube_auth


class _FakeResponse:
    def __init__(self, *, status_code=200, text="", json_data=None, json_error=False):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _envelope_response(payload):
    return _FakeResponse(status_code=200, text=json.dumps(payload), json_data=payload)


def test_is_configured_reflects_base_url(monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "")
    assert cube_auth.is_configured() is False
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    assert cube_auth.is_configured() is True


def test_request_code_fails_cleanly_when_base_url_unset(monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "")
    result = cube_auth.request_code("09120000000")
    assert isinstance(result, cube_auth.AuthError)
    assert result.code == "network"


def test_request_code_success(monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    captured = {}

    def fake_request(method, url, json=None, headers=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _envelope_response({"ok": True, "cooldown_seconds": 45})

    monkeypatch.setattr(cube_auth.requests, "request", fake_request)

    result = cube_auth.request_code("09120000000")

    assert isinstance(result, cube_auth.RequestCodeOk)
    assert result.cooldown_seconds == 45
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.example.com/api/requestcode.php"
    assert captured["json"] == {"identifier": "09120000000"}
    assert "Authorization" not in captured["headers"]


def test_request_code_error_envelope(monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(
        cube_auth.requests, "request",
        lambda *a, **k: _envelope_response({"ok": False, "error": "rate_limited", "message": "Too many requests"}),
    )

    result = cube_auth.request_code("09120000000")

    assert isinstance(result, cube_auth.AuthError)
    assert result.code == "rate_limited"
    assert result.message == "Too many requests"


def test_verify_code_success_defaults_identifier_when_missing(monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(
        cube_auth.requests, "request",
        lambda *a, **k: _envelope_response({
            "ok": True, "token": "tok-123",
            "user": {"id": "u1", "display_name": "Reza"},
        }),
    )

    result = cube_auth.verify_code("09120000000", "12345")

    assert isinstance(result, cube_auth.VerifyOk)
    assert result.token == "tok-123"
    assert result.user.display_name == "Reza"
    assert result.user.identifier == "09120000000"


def test_verify_code_malformed_response_without_token(monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(
        cube_auth.requests, "request",
        lambda *a, **k: _envelope_response({"ok": True}),
    )

    result = cube_auth.verify_code("09120000000", "12345")

    assert isinstance(result, cube_auth.AuthError)
    assert result.code == "bad_response"


def test_fetch_account_parses_services_and_sends_bearer_token(monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    captured = {}

    def fake_request(method, url, json=None, headers=None, timeout=None):
        captured["headers"] = headers
        return _envelope_response({
            "ok": True,
            "user": {"id": "u1", "identifier": "09120000000"},
            "services": [
                {"id": "s1", "name": "Plan A", "subscription_url": "https://sub.example/a",
                 "expire": 123, "total_bytes": 100, "used_bytes": 10},
                "not-a-dict",
            ],
        })

    monkeypatch.setattr(cube_auth.requests, "request", fake_request)

    result = cube_auth.fetch_account("tok-123")

    assert isinstance(result, cube_auth.AccountOk)
    assert len(result.services) == 1
    assert result.services[0].name == "Plan A"
    assert result.services[0].subscription_url == "https://sub.example/a"
    assert captured["headers"]["Authorization"] == "Bearer tok-123"


def test_send_handles_network_exception(monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")

    def raise_connection_error(*a, **k):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(cube_auth.requests, "request", raise_connection_error)

    result = cube_auth.request_code("09120000000")

    assert isinstance(result, cube_auth.AuthError)
    assert result.code == "network"
    assert "boom" in result.message


def test_fetch_subscription_uris_decodes_base64(monkeypatch):
    body = "vless://a@example.com:443?security=tls#one\ntrojan://b@example.com:443?security=tls#two"
    encoded = base64.b64encode(body.encode("utf-8")).decode("ascii")
    monkeypatch.setattr(
        cube_auth.requests, "get",
        lambda url, timeout=None: _FakeResponse(status_code=200, text=encoded),
    )

    uris = cube_auth.fetch_subscription_uris("https://sub.example/a")

    assert uris == [
        "vless://a@example.com:443?security=tls#one",
        "trojan://b@example.com:443?security=tls#two",
    ]


def test_fetch_subscription_uris_accepts_plain_text(monkeypatch):
    monkeypatch.setattr(
        cube_auth.requests, "get",
        lambda url, timeout=None: _FakeResponse(status_code=200, text="not-base64-!!!\nvless://x@y:443#z"),
    )

    uris = cube_auth.fetch_subscription_uris("https://sub.example/a")

    assert uris == ["not-base64-!!!", "vless://x@y:443#z"]
