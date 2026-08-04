"""Auto Mode has to be able to reach the configs the user actually added.

A tester with two working configs in the Manual tab and Auto Mode on was told
"User Config has no verified route for Auto Mode yet" and the home page counted
"0 verified configs". Both were true statements about a pool that could never
be non-empty:

  * Auto Mode looked only at profiles whose origin is USER_CONFIG_ORIGIN, so a
    config pasted into Manual was never a candidate; and
  * it then kept only profiles where ``route_is_verified``, which nothing sets
    except the app's own bundled spoof configs — an imported or pasted config
    can only become verified by connecting through it once.

So on a fresh install the pool was empty on every platform. This was reported
on macOS first and reproduced on Windows.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

from PySide6.QtGui import QIcon

import uac_desktop.ui as ui_module
from uac_desktop.ui import MainWindow, USER_CONFIG_ORIGIN

from test_profile_source_routing import (
    ComboStub,
    LabelStub,
    StorageStub,
    profile,
    routing_dummy,
)


def _auto_order(storage, monkeypatch):
    dummy = routing_dummy(storage, source_index=1)
    monkeypatch.setattr(ui_module, "profile_ping", lambda *_args: (True, 10.0))
    return MainWindow._ordered_profiles(
        dummy, "static.cloudflare.com", threading.Event(), auto_enabled=True
    )


def test_a_config_added_in_the_manual_tab_is_a_candidate(monkeypatch):
    """The exact reported shape: two Manual configs, Auto Mode on, no country."""
    first = profile("bratwurst-one", origin="user")
    second = profile("bratwurst-two", origin="user")
    storage = StorageStub([first, second])

    ordered = _auto_order(storage, monkeypatch)

    assert {item.id for item in ordered} == {first.id, second.id}


def test_an_untested_config_is_tried_rather_than_refused(monkeypatch):
    """Verification is the *result* of connecting, so it cannot be the gate."""
    untested = profile("untested-user-config", origin=USER_CONFIG_ORIGIN)
    storage = StorageStub([untested])

    assert _auto_order(storage, monkeypatch) == [untested]


def test_verified_configs_still_win_when_there_are_any(monkeypatch):
    """The fallback must not cost verified routes their priority."""
    verified = profile("verified-one", origin=USER_CONFIG_ORIGIN, verified=True, ping=40)
    untested = profile("untested-one", origin="user")
    storage = StorageStub([untested, verified])

    assert _auto_order(storage, monkeypatch) == [verified]


def test_bundled_spoof_profiles_stay_out_of_the_user_route_pool(monkeypatch):
    """Widening to Manual must not also pull in the app's own suggestions."""
    bundled = profile("suggested", origin="verified", verified=True, ping=15)
    mine = profile("mine", origin="user")
    storage = StorageStub([bundled, mine])

    assert _auto_order(storage, monkeypatch) == [mine]


def _connect_gate(storage):
    """The precondition in toggle_connection, evaluated the way it is there."""
    dummy = routing_dummy(storage, source_index=1)
    return not dummy._route_source_profiles()


def test_connect_is_refused_only_when_there_is_nothing_at_all():
    assert _connect_gate(StorageStub([]))
    assert not _connect_gate(StorageStub([profile("mine", origin="user")]))
    assert not _connect_gate(
        StorageStub([profile("imported", origin=USER_CONFIG_ORIGIN)])
    )


def test_the_home_counter_counts_untested_configs_instead_of_zero(monkeypatch):
    """"0 verified configs" above a list of two reads as a broken app."""
    storage = StorageStub([
        profile("one", origin="user"),
        profile("two", origin="user"),
    ])
    dummy = routing_dummy(storage, source_index=1)
    dummy.country_combo = ComboStub()
    dummy.country_count = LabelStub()
    dummy.language = "en"
    dummy.tr = lambda _fa, en=None: en or _fa
    dummy._country_metadata = lambda code: MainWindow._country_metadata(dummy, code)
    dummy._country_profiles = lambda code=None: MainWindow._country_profiles(dummy, code)
    monkeypatch.setattr(ui_module, "country_flag_icon", lambda *_args: QIcon())
    monkeypatch.setattr(ui_module, "cyber_icon", lambda *_args: QIcon())

    MainWindow._refresh_country_selector(dummy)

    assert dummy.country_count.text == "2 configs · not tested"


def test_the_counter_reports_verified_routes_once_there_are_some(monkeypatch):
    storage = StorageStub([
        profile("one", origin="user"),
        profile("two", origin=USER_CONFIG_ORIGIN, verified=True, ping=40),
    ])
    dummy = routing_dummy(storage, source_index=1)
    dummy.country_combo = ComboStub()
    dummy.country_count = LabelStub()
    dummy.language = "en"
    dummy.tr = lambda _fa, en=None: en or _fa
    dummy._country_metadata = lambda code: MainWindow._country_metadata(dummy, code)
    dummy._country_profiles = lambda code=None: MainWindow._country_profiles(dummy, code)
    monkeypatch.setattr(ui_module, "country_flag_icon", lambda *_args: QIcon())
    monkeypatch.setattr(ui_module, "cyber_icon", lambda *_args: QIcon())

    MainWindow._refresh_country_selector(dummy)

    assert dummy.country_count.text == "1 verified configs"


def test_an_empty_library_still_reports_zero(monkeypatch):
    dummy = routing_dummy(StorageStub([]), source_index=1)
    dummy.country_combo = ComboStub()
    dummy.country_count = LabelStub()
    dummy.language = "en"
    dummy.tr = lambda _fa, en=None: en or _fa
    dummy._country_metadata = lambda code: MainWindow._country_metadata(dummy, code)
    dummy._country_profiles = lambda code=None: MainWindow._country_profiles(dummy, code)
    monkeypatch.setattr(ui_module, "country_flag_icon", lambda *_args: QIcon())
    monkeypatch.setattr(ui_module, "cyber_icon", lambda *_args: QIcon())

    MainWindow._refresh_country_selector(dummy)

    assert dummy.country_count.text == "0 verified configs"


def test_verified_route_is_written_by_something(monkeypatch):
    """The flag existed, was reset on edit, and was never set to True.

    Without a writer, `route_is_verified` is permanently False for any config
    a user supplies, which is what made both the candidate filter and the home
    counter stick at zero forever.
    """
    import pathlib
    import re

    source = pathlib.Path(ui_module.__file__).read_text(encoding="utf-8")
    writes = re.findall(r"verified_route\s*=\s*(True|False)", source)
    assert "True" in writes, writes


def test_a_proven_route_keeps_its_measured_latency(monkeypatch):
    """The edge ping is a worse number than a real tunnel measurement."""
    proven = profile("proven", origin="user", verified=True, ping=42)
    proven.verified_route = True
    storage = StorageStub([proven])
    dummy = routing_dummy(storage, source_index=1)
    monkeypatch.setattr(ui_module, "profile_ping", lambda *_args: (True, 999.0))

    MainWindow._ordered_profiles(
        dummy, "static.cloudflare.com", threading.Event(), auto_enabled=True
    )

    assert proven.last_ping_ms == 42


def test_nothing_here_depends_on_the_host_platform():
    """Reported on macOS, reproduced on Windows — the pool is platform-blind."""
    import inspect

    source = inspect.getsource(MainWindow._route_source_profiles)
    for token in ("os.name", "sys.platform", "detect_host", "platform_support"):
        assert token not in source, token
