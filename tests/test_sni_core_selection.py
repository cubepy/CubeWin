from __future__ import annotations

import socket

import pytest

import uac_desktop.engine as engine_module
import uac_desktop.platform_support as ps
from uac_desktop.engine import select_sni_core
from uac_desktop.fragment_proxy import FragmentProxy
from uac_desktop.models import ProxyProfile, Tuning
from uac_desktop.pattern_core import PatternSniCore


def _host(supported: bool):
    return ps.HostArchitecture(
        native="x64", process="x64", emulated=False,
        supported=supported, reason="" if supported else "not-windows",
    )


def test_windows_keeps_the_wrong_sequence_core(monkeypatch):
    monkeypatch.setattr(engine_module, "detect_host", lambda: _host(True))
    assert isinstance(select_sni_core(lambda _m: None), PatternSniCore)


def test_a_host_without_windivert_falls_back_rather_than_giving_up(monkeypatch):
    """The point of the change: no driver means the weaker core, not no core."""
    monkeypatch.setattr(engine_module, "detect_host", lambda: _host(False))
    assert isinstance(select_sni_core(lambda _m: None), FragmentProxy)


def test_the_choice_is_written_to_the_log(monkeypatch):
    """Which core is running has to be visible in a bug report."""
    for supported, expected in ((True, "wrong-sequence"), (False, "fragmentation")):
        monkeypatch.setattr(engine_module, "detect_host", lambda s=supported: _host(s))
        lines = []
        select_sni_core(lines.append)
        assert any(expected in line for line in lines), (supported, lines)


def test_both_cores_present_the_same_interface_to_the_engine():
    """The engine calls only start/stop, and swaps one for the other blind."""
    for core in (PatternSniCore, FragmentProxy):
        assert callable(getattr(core, "start"))
        assert callable(getattr(core, "stop"))
        assert isinstance(getattr(core, "running"), property)


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_the_fallback_core_actually_listens_where_xray_expects_it():
    """Xray dials 127.0.0.1:<config_port>; the fallback must answer there."""
    port = _free_port()
    core = FragmentProxy(lambda _m: None)
    core.start(ProxyProfile(config_port=port), Tuning())
    try:
        with socket.socket() as client:
            client.settimeout(3)
            assert client.connect_ex(("127.0.0.1", port)) == 0
    finally:
        core.stop()


def test_the_fallback_core_needs_no_windows_api():
    source = (
        __import__("pathlib").Path(engine_module.__file__).parent / "fragment_proxy.py"
    ).read_text()
    for forbidden in ("windll", "winreg", "pydivert", "WinDivert"):
        assert forbidden not in source, forbidden
