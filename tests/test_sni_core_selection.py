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


def test_the_selected_core_carries_a_label_for_the_log(monkeypatch):
    """The choice is made before the UI can listen for log lines.

    select_sni_core runs inside Engine.__init__, which happens before _wire()
    connects the log handler — so anything it logs there is emitted into
    nothing. The label is recorded on the core instead, for the UI to report
    once it is listening.
    """
    for supported, expected in ((True, "wrong-sequence"), (False, "fragmentation")):
        monkeypatch.setattr(engine_module, "detect_host", lambda s=supported: _host(s))
        core = select_sni_core(lambda _m: None)
        label = getattr(core, "selection_label", "")
        assert expected in label, (supported, label)


def test_startup_log_does_not_contradict_the_active_core(monkeypatch, tmp_path):
    """The host line used to end in "UNSUPPORTED" while the fallback ran."""
    import uac_desktop.ui as ui_module

    monkeypatch.setattr(engine_module, "detect_host", lambda: _host(False))
    monkeypatch.setattr(ui_module.MainWindow, "_setup_tray", lambda self: None)
    monkeypatch.setattr(ui_module.MainWindow, "refresh_processes", lambda self: None)
    monkeypatch.setattr(
        ui_module.MainWindow, "check_for_updates", lambda self, manual=False: None)
    monkeypatch.setenv("CUBEVPN_DATA_DIR", str(tmp_path))

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    window = ui_module.MainWindow()
    try:
        app.processEvents()
        joined = "\n".join(window._all_log_lines)
        assert "UNSUPPORTED" not in joined, joined
        assert "SNI core:" in joined, joined
    finally:
        window._force_quit = True
        window.close()


def test_windows_only_controls_are_locked_and_explain_themselves(
        monkeypatch, tmp_path):
    """Say it on the control, not in a banner.

    A modal blocked the tour behind it; a permanent activity-bar line read as
    a stuck error, because that bar reports current activity and this is a
    fact about the machine. A disabled switch with a tooltip says it where the
    user reaches for the thing that cannot work.
    """
    import uac_desktop.ui as ui_module

    monkeypatch.setattr(engine_module, "detect_host", lambda: _host(False))
    monkeypatch.setattr(ui_module, "detect_host", lambda: _host(False))
    monkeypatch.setattr(ui_module.MainWindow, "_setup_tray", lambda self: None)
    monkeypatch.setattr(ui_module.MainWindow, "refresh_processes", lambda self: None)
    monkeypatch.setattr(
        ui_module.MainWindow, "check_for_updates", lambda self, manual=False: None)
    monkeypatch.setenv("CUBEVPN_DATA_DIR", str(tmp_path))

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    window = ui_module.MainWindow()
    try:
        window._warn_unsupported_architecture()
        app.processEvents()
        controls = (window.proxy_option, window.proxy_mode,
                    window.tun_option, window.tun_mode,
                    window.gateway_option, window.gateway_mode)
        assert not any(c.isEnabled() for c in controls)
        for control in controls:
            assert control.toolTip().strip(), control.objectName()

        # The state updates that used to hand these back must not.
        window._set_state(False)
        app.processEvents()
        assert not any(c.isEnabled() for c in controls)

        # And nothing may be left sitting in the activity bar as a fake error.
        assert "WinDivert" not in window.activity_bar.message.text()
    finally:
        window._force_quit = True
        window.close()


def test_a_windows_host_keeps_its_controls(monkeypatch, tmp_path):
    import uac_desktop.ui as ui_module

    monkeypatch.setattr(engine_module, "detect_host", lambda: _host(True))
    monkeypatch.setattr(ui_module, "detect_host", lambda: _host(True))
    monkeypatch.setattr(ui_module.MainWindow, "_setup_tray", lambda self: None)
    monkeypatch.setattr(ui_module.MainWindow, "refresh_processes", lambda self: None)
    monkeypatch.setattr(
        ui_module.MainWindow, "check_for_updates", lambda self, manual=False: None)
    monkeypatch.setenv("CUBEVPN_DATA_DIR", str(tmp_path))

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    window = ui_module.MainWindow()
    try:
        window._warn_unsupported_architecture()
        app.processEvents()
        assert window.gateway_option.isEnabled()
        assert window.tun_option.isEnabled()
    finally:
        window._force_quit = True
        window.close()
