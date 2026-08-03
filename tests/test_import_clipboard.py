import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

import uac_desktop.ui as ui_module
from uac_desktop.ui import MainWindow


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


class _ClipboardStub:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


def _dummy(clipboard_text):
    worker = ui_module._SubscriptionImportWorker()
    activities = []
    errors = []
    toasts = []
    dummy = SimpleNamespace(
        storage=SimpleNamespace(profiles=[], save_profiles=lambda: None),
        clip_btn=SimpleNamespace(setEnabled=lambda _v: None),
        _subscription_import_worker=worker,
        refresh_profiles=lambda: None,
        _set_activity=lambda *a: activities.append(a),
        _handle_error=lambda message: errors.append(message),
        show_toast=lambda message, kind="success": toasts.append((message, kind)),
        tr=lambda fa, en=None: en or fa,
    )
    dummy._finish_clipboard_import = lambda profiles: MainWindow._finish_clipboard_import(dummy, profiles)
    dummy._on_subscription_import_done = lambda profiles, error: MainWindow._on_subscription_import_done(dummy, profiles, error)
    worker.done.connect(lambda profiles, error: MainWindow._on_subscription_import_done(dummy, profiles, error))
    monkeypatch_target = SimpleNamespace(clipboard=lambda: _ClipboardStub(clipboard_text))
    return dummy, monkeypatch_target, errors, toasts


def test_import_clipboard_with_direct_uris_skips_network(app, monkeypatch):
    dummy, clip, errors, toasts = _dummy(
        "vless://11111111-1111-1111-1111-111111111111@a.example.com:443?security=tls&sni=a.example.com#one"
    )
    monkeypatch.setattr(ui_module, "QApplication", clip)
    called = []
    monkeypatch.setattr(ui_module, "fetch_subscription_uris", lambda url: called.append(url) or [])

    MainWindow.import_clipboard(dummy)

    assert not called
    assert not errors
    assert len(dummy.storage.profiles) == 1
    assert toasts and "1" in toasts[0][0]


def test_import_clipboard_fetches_subscription_link(app, monkeypatch):
    dummy, clip, errors, toasts = _dummy("https://sub.example.com/link/abc123")
    monkeypatch.setattr(ui_module, "QApplication", clip)
    monkeypatch.setattr(
        ui_module, "fetch_subscription_uris",
        lambda url: ["vless://22222222-2222-2222-2222-222222222222@b.example.com:443?security=tls&sni=b.example.com#two"],
    )

    MainWindow.import_clipboard(dummy)

    assert not errors
    assert len(dummy.storage.profiles) == 1
    assert dummy.storage.profiles[0].name == "two"


def test_import_clipboard_reports_error_when_subscription_fetch_fails(app, monkeypatch):
    dummy, clip, errors, toasts = _dummy("https://sub.example.com/link/abc123")
    monkeypatch.setattr(ui_module, "QApplication", clip)

    def boom(url):
        raise RuntimeError("network down")

    monkeypatch.setattr(ui_module, "fetch_subscription_uris", boom)

    MainWindow.import_clipboard(dummy)

    assert errors
    assert dummy.storage.profiles == []


def test_import_clipboard_rejects_text_that_is_neither_config_nor_url(app, monkeypatch):
    dummy, clip, errors, toasts = _dummy("this is just some random text")
    monkeypatch.setattr(ui_module, "QApplication", clip)
    called = []
    monkeypatch.setattr(ui_module, "fetch_subscription_uris", lambda url: called.append(url) or [])

    MainWindow.import_clipboard(dummy)

    assert not called
    assert errors
    assert dummy.storage.profiles == []
