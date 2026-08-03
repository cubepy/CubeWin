import base64
import json

from uac_desktop.engine import build_xray_config
from uac_desktop.models import parse_many, parse_outbound, parse_uri


def _vmess_uri(**overrides):
    payload = {
        "v": "2", "ps": "test-vmess", "add": "example.com", "port": "8443",
        "id": "11111111-1111-1111-1111-111111111111", "aid": "0", "scy": "auto",
        "net": "ws", "type": "none", "host": "cdn.example.com", "path": "/ws",
        "tls": "tls", "sni": "sni.example.com",
    }
    payload.update(overrides)
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    return f"vmess://{encoded}"


def test_vmess_base64_json_uri_parses_into_a_working_profile():
    profile = parse_uri(_vmess_uri())

    assert profile is not None
    assert profile.protocol == "vmess"
    assert profile.name == "test-vmess"
    assert profile.config_host == "example.com"
    assert profile.config_port == 8443
    assert profile.sni == "sni.example.com"


def test_vmess_base64_json_uri_builds_a_valid_xray_outbound():
    profile = parse_uri(_vmess_uri())
    outbound = parse_outbound(profile)

    assert outbound["user"] == "11111111-1111-1111-1111-111111111111"
    assert outbound["host"] == "example.com"
    assert outbound["port"] == 8443
    assert outbound["network"] == "ws"
    assert outbound["security"] == "tls"
    assert outbound["host_header"] == "cdn.example.com"
    assert outbound["path"] == "/ws"

    config = build_xray_config(profile)
    outbound_config = config["outbounds"][0]
    assert outbound_config["protocol"] == "vmess"
    assert outbound_config["settings"]["vnext"][0]["users"][0]["id"] == (
        "11111111-1111-1111-1111-111111111111"
    )
    assert outbound_config["streamSettings"]["wsSettings"]["path"] == "/ws"
    assert outbound_config["streamSettings"]["tlsSettings"]["serverName"] == "sni.example.com"


def test_vmess_grpc_uses_path_as_service_name_when_no_explicit_field():
    profile = parse_uri(_vmess_uri(net="grpc", host="", path="GunService"))
    config = build_xray_config(profile)

    assert config["outbounds"][0]["streamSettings"]["grpcSettings"]["serviceName"] == "GunService"


def test_vmess_plain_tcp_with_no_tls_produces_raw_unencrypted_stream():
    profile = parse_uri(_vmess_uri(net="tcp", type="none", tls="", host="", path=""))
    config = build_xray_config(profile)

    stream = config["outbounds"][0]["streamSettings"]
    assert stream["network"] == "raw"
    assert stream["security"] == "none"
    assert "tlsSettings" not in stream


def test_vmess_malformed_base64_is_rejected_not_silently_mangled():
    assert parse_uri("vmess://not-valid-base64-json!!!") is None


def test_vmess_query_string_style_uri_still_parses_unchanged():
    uri = "vmess://11111111-1111-1111-1111-111111111111@example.com:443?type=ws&security=tls&host=cdn.example.com&path=/ws&sni=sni.example.com#classic"
    profile = parse_uri(uri)

    assert profile is not None
    assert profile.protocol == "vmess"
    assert profile.name == "classic"
    assert profile.config_host == "example.com"


def test_shadowsocks_sip002_uri_parses_and_builds_shadowsocks_outbound():
    userinfo = base64.urlsafe_b64encode(b"aes-256-gcm:supersecret").decode().rstrip("=")
    uri = f"ss://{userinfo}@ss.example.com:8388#My%20SS"

    profile = parse_uri(uri)
    assert profile is not None
    assert profile.protocol == "ss"
    assert profile.name == "My SS"
    assert profile.config_host == "ss.example.com"
    assert profile.config_port == 8388

    outbound = parse_outbound(profile)
    assert outbound["user"] == "aes-256-gcm"
    assert outbound["password"] == "supersecret"
    assert outbound["network"] == "raw"
    assert outbound["security"] == "none"

    config = build_xray_config(profile)
    outbound_config = config["outbounds"][0]
    assert outbound_config["protocol"] == "shadowsocks"
    assert outbound_config["settings"]["servers"][0] == {
        "address": "ss.example.com", "port": 8388,
        "method": "aes-256-gcm", "password": "supersecret",
    }
    assert outbound_config["streamSettings"]["security"] == "none"


def test_shadowsocks_legacy_fully_encoded_uri_parses():
    legacy = base64.b64encode(
        b"chacha20-ietf-poly1305:anotherpass@legacy.example.com:8389"
    ).decode()
    uri = f"ss://{legacy}#Legacy"

    profile = parse_uri(uri)
    assert profile is not None
    outbound = parse_outbound(profile)
    assert outbound["user"] == "chacha20-ietf-poly1305"
    assert outbound["password"] == "anotherpass"
    assert outbound["host"] == "legacy.example.com"
    assert outbound["port"] == 8389


def test_shadowsocks_password_with_special_characters_round_trips():
    userinfo = base64.urlsafe_b64encode(b"aes-128-gcm:p@ss:w/rd").decode().rstrip("=")
    uri = f"ss://{userinfo}@ss.example.com:8388#special"

    profile = parse_uri(uri)
    outbound = parse_outbound(profile)
    assert outbound["user"] == "aes-128-gcm"
    assert outbound["password"] == "p@ss:w/rd"


def test_shadowsocks_missing_port_is_rejected():
    userinfo = base64.urlsafe_b64encode(b"aes-256-gcm:pw").decode().rstrip("=")
    assert parse_uri(f"ss://{userinfo}@ss.example.com") is None


def test_parse_many_extracts_all_four_protocols_from_a_subscription_blob():
    vless = "vless://11111111-1111-1111-1111-111111111111@a.example.com:443?security=tls&sni=a.example.com#vless-one"
    trojan = "trojan://password@b.example.com:443?security=tls&sni=b.example.com#trojan-one"
    vmess = _vmess_uri(ps="vmess-one")
    ss_userinfo = base64.urlsafe_b64encode(b"aes-256-gcm:pw").decode().rstrip("=")
    ss = f"ss://{ss_userinfo}@c.example.com:8388#ss-one"

    blob = "\n".join([vless, trojan, vmess, ss])
    profiles = parse_many(blob)

    assert [p.protocol for p in profiles] == ["vless", "trojan", "vmess", "ss"]
    assert [p.name for p in profiles] == ["vless-one", "trojan-one", "vmess-one", "ss-one"]
