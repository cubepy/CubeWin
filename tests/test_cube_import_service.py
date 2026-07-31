import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

import uac_desktop.ui as ui_module
from uac_desktop import cube_auth
from uac_desktop.models import ProxyProfile
from uac_desktop.ui import USER_CONFIG_ORIGIN, MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _SyncThread:
    def __init__(self, target=None, name=None, daemon=None, args=(), kwargs=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


@pytest.fixture(autouse=True)
def _sync_threads(monkeypatch):
    monkeypatch.setattr(ui_module.threading, "Thread", _SyncThread)


def _dummy():
    worker = ui_module._CubeImportWorker()
    refreshed = []
    dummy = SimpleNamespace(
        storage=SimpleNamespace(profiles=[], save_profiles=lambda: None),
        _cube_import_worker=worker,
        refresh_profiles=lambda: refreshed.append(True),
    )
    worker.done.connect(lambda callback, ok: MainWindow._on_cube_import_done(dummy, callback, ok))
    return dummy, refreshed


def test_import_cube_service_adds_new_profile_with_user_config_origin(app, monkeypatch):
    dummy, refreshed = _dummy()
    monkeypatch.setattr(
        cube_auth, "fetch_subscription_uris",
        lambda url: ["vless://a@example.com:443?security=tls#one"],
    )
    results = []

    MainWindow._import_cube_service(
        dummy,
        cube_auth.CubeAccountService(id="s1", subscription_url="https://sub.example/a"),
        results.append,
    )

    assert results == [True]
    assert len(dummy.storage.profiles) == 1
    assert dummy.storage.profiles[0].origin == USER_CONFIG_ORIGIN
    assert refreshed == [True]


def test_import_cube_service_dedupes_existing_source_uri(app, monkeypatch):
    dummy, refreshed = _dummy()
    existing = ProxyProfile(
        id="p1", source_uri="vless://a@example.com:443?security=tls#one",
        origin=USER_CONFIG_ORIGIN,
    )
    dummy.storage.profiles.append(existing)
    monkeypatch.setattr(
        cube_auth, "fetch_subscription_uris",
        lambda url: ["vless://a@example.com:443?security=tls#one"],
    )
    results = []

    MainWindow._import_cube_service(
        dummy,
        cube_auth.CubeAccountService(id="s1", subscription_url="https://sub.example/a"),
        results.append,
    )

    assert results == [True]
    assert len(dummy.storage.profiles) == 1


def test_import_cube_service_reports_failure_without_touching_storage(app, monkeypatch):
    dummy, refreshed = _dummy()

    def boom(url):
        raise RuntimeError("network down")

    monkeypatch.setattr(cube_auth, "fetch_subscription_uris", boom)
    results = []

    MainWindow._import_cube_service(
        dummy,
        cube_auth.CubeAccountService(id="s1", subscription_url="https://sub.example/a"),
        results.append,
    )

    assert results == [False]
    assert dummy.storage.profiles == []
    assert refreshed == []
