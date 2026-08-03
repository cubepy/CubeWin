"""Client for the CubeVPN account API (Telegram OTP sign-in).

Talks to the same requestcode.php / verifycode.php / accountme.php contract
as the CubeVPN Android app and the CubeVPN Windows/WPF client, so every
CubeVPN client speaks the same backend contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from .app_config import CUBE_API_BASE_URL

_TIMEOUT = 12

# Talks to the account API directly, never through the local VPN tunnel —
# trust_env=False keeps it from inheriting the Windows System Proxy this app
# itself sets while connected (which can include a SOCKS entry requests
# can't use without PySocks).
_session = requests.Session()
_session.trust_env = False


@dataclass
class CubeAuthUser:
    id: str = ""
    identifier: str = ""
    display_name: str = ""

    @classmethod
    def from_dict(cls, raw: dict) -> "CubeAuthUser":
        raw = raw if isinstance(raw, dict) else {}
        return cls(
            id=str(raw.get("id", "") or ""),
            identifier=str(raw.get("identifier", "") or ""),
            display_name=str(raw.get("display_name", "") or ""),
        )


@dataclass
class CubeAccountService:
    id: str = ""
    name: str = ""
    subscription_url: str = ""
    expire: int = 0
    total_bytes: int = 0
    used_bytes: int = 0

    @classmethod
    def from_dict(cls, raw: dict) -> "CubeAccountService":
        raw = raw if isinstance(raw, dict) else {}
        return cls(
            id=str(raw.get("id", "") or ""),
            name=str(raw.get("name", "") or ""),
            subscription_url=str(raw.get("subscription_url", "") or ""),
            expire=int(raw.get("expire", 0) or 0),
            total_bytes=int(raw.get("total_bytes", 0) or 0),
            used_bytes=int(raw.get("used_bytes", 0) or 0),
        )


@dataclass
class RequestCodeOk:
    cooldown_seconds: int = 60


@dataclass
class VerifyOk:
    token: str = ""
    user: CubeAuthUser = field(default_factory=CubeAuthUser)


@dataclass
class AccountOk:
    user: CubeAuthUser = field(default_factory=CubeAuthUser)
    services: list[CubeAccountService] = field(default_factory=list)


@dataclass
class AuthError:
    code: str = "unknown"
    message: str = "Request failed"


def is_configured() -> bool:
    return bool(CUBE_API_BASE_URL.strip())


def _network_error(detail: str) -> AuthError:
    return AuthError(code="network", message=f"Network error — {detail}")


def _send(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    """Never raises — network/parse failures come back as a synthetic ok:false envelope."""
    base = CUBE_API_BASE_URL.strip().rstrip("/")
    if not base:
        return {"ok": False, "error": "network", "message": "API base URL is not configured in this build"}
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = _session.request(
            method, base + path, json=body, headers=headers, timeout=_TIMEOUT,
        )
        text = response.text
        if not text:
            return {
                "ok": False, "error": "network",
                "message": f"server returned HTTP {response.status_code} with an empty body",
            }
        try:
            data = response.json()
        except ValueError:
            snippet = text if len(text) <= 200 else text[:200]
            return {
                "ok": False, "error": "network",
                "message": f"HTTP {response.status_code}, non-JSON response: {snippet}",
            }
        return data if isinstance(data, dict) else {"ok": False, "error": "network", "message": "empty JSON"}
    except requests.RequestException as exc:
        return {"ok": False, "error": "network", "message": f"{type(exc).__name__}: {exc}"}


def _error_from(env: dict) -> AuthError:
    return AuthError(
        code=str(env.get("error") or "unknown"),
        message=str(env.get("message") or "Request failed"),
    )


def request_code(identifier: str) -> RequestCodeOk | AuthError:
    env = _send("POST", "/api/requestcode.php", {"identifier": identifier})
    if not env.get("ok"):
        return _error_from(env)
    return RequestCodeOk(cooldown_seconds=int(env.get("cooldown_seconds", 60) or 60))


def verify_code(identifier: str, code: str) -> VerifyOk | AuthError:
    env = _send("POST", "/api/verifycode.php", {"identifier": identifier, "code": code})
    if not env.get("ok"):
        return _error_from(env)
    token = str(env.get("token", "") or "")
    raw_user = env.get("user")
    if not token or not isinstance(raw_user, dict):
        return AuthError(code="bad_response", message="Malformed server response")
    user = CubeAuthUser.from_dict(raw_user)
    if not user.identifier:
        user.identifier = identifier
    return VerifyOk(token=token, user=user)


def fetch_account(token: str) -> AccountOk | AuthError:
    env = _send("GET", "/api/accountme.php", None, token)
    if not env.get("ok"):
        return _error_from(env)
    raw_services = env.get("services")
    services = [
        CubeAccountService.from_dict(item)
        for item in raw_services if isinstance(item, dict)
    ] if isinstance(raw_services, list) else []
    return AccountOk(user=CubeAuthUser.from_dict(env.get("user") or {}), services=services)


def logout(token: str) -> None:
    try:
        _send("POST", "/api/logout.php", {}, token)
    except Exception:
        pass


def fetch_subscription_uris(url: str, timeout: int = 15) -> list[str]:
    """Fetch a v2ray-style subscription link and return its config URIs.

    Delegates to :mod:`uac_desktop.network`, which every other subscription
    consumer in the app (manual "Import from Clipboard") also uses.
    """
    from . import network

    return network.fetch_subscription_uris(url, timeout=timeout)
