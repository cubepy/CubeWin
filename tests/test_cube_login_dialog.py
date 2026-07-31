import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog

import uac_desktop.ui as ui_module
from uac_desktop import cube_auth
from uac_desktop.ui import CubeLoginDialog


class _SyncThread:
    """Runs the target immediately on the calling thread instead of a real one.

    The dialog's network calls are already monkeypatched to be instant and
    side-effect-free in these tests, so running "in the background"
    synchronously removes the race between the worker thread emitting its
    signal and the test calling ``app.processEvents()``.
    """

    def __init__(self, target=None, name=None, daemon=None, args=(), kwargs=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture(autouse=True)
def _synchronous_background_threads(monkeypatch):
    monkeypatch.setattr(ui_module.threading, "Thread", _SyncThread)


def test_dialog_disables_sign_in_when_backend_not_configured(app, monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "")
    dialog = CubeLoginDialog(None, "en")
    dialog.show()
    try:
        assert not dialog.primary_button.isEnabled()
        assert not dialog.identifier_field.isEnabled()
        assert dialog.error_label.isVisible()
    finally:
        dialog.deleteLater()


def test_request_code_success_moves_to_code_step_and_starts_cooldown(app, monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(
        cube_auth, "request_code",
        lambda identifier: cube_auth.RequestCodeOk(cooldown_seconds=30),
    )
    dialog = CubeLoginDialog(None, "en")
    dialog.show()
    try:
        dialog.identifier_field.setText("09120000000")
        dialog._request_code()
        app.processEvents()

        assert dialog.step1.isVisible() is False
        assert dialog.step2.isVisible() is True
        assert dialog._identifier == "09120000000"
        assert dialog.primary_button.text() == "Verify Code"
        assert dialog.resend_button.isEnabled() is False
        assert dialog._cooldown_seconds == 30
    finally:
        dialog._cooldown_timer.stop()
        dialog.deleteLater()


def test_request_code_error_shows_message_and_stays_on_step1(app, monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(
        cube_auth, "request_code",
        lambda identifier: cube_auth.AuthError(code="rate_limited", message="Too many requests"),
    )
    dialog = CubeLoginDialog(None, "en")
    dialog.show()
    try:
        dialog.identifier_field.setText("09120000000")
        dialog._request_code()
        app.processEvents()

        assert dialog.step1.isVisible() is True
        assert dialog.step2.isVisible() is False
        assert dialog.error_label.text() == "Too many requests"
        assert dialog.error_label.isVisible() is True
    finally:
        dialog.deleteLater()


def test_verify_code_success_stores_token_and_accepts(app, monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    user = cube_auth.CubeAuthUser(id="u1", identifier="09120000000", display_name="Reza")
    monkeypatch.setattr(
        cube_auth, "verify_code",
        lambda identifier, code: cube_auth.VerifyOk(token="tok-abc", user=user),
    )
    dialog = CubeLoginDialog(None, "en")
    try:
        dialog._identifier = "09120000000"
        dialog.code_field.setText("12345")
        results = []
        dialog.finished.connect(results.append)
        dialog._verify_code()
        app.processEvents()

        assert dialog.token == "tok-abc"
        assert dialog.user is user
        assert results and results[0] == QDialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()


def test_verify_code_error_shows_message(app, monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(
        cube_auth, "verify_code",
        lambda identifier, code: cube_auth.AuthError(code="invalid_code", message="Wrong code"),
    )
    dialog = CubeLoginDialog(None, "en")
    try:
        dialog._identifier = "09120000000"
        dialog.code_field.setText("00000")
        dialog._verify_code()
        app.processEvents()

        assert dialog.token == ""
        assert dialog.error_label.text() == "Wrong code"
    finally:
        dialog.deleteLater()


def test_change_number_returns_to_step1_and_stops_cooldown(app, monkeypatch):
    monkeypatch.setattr(cube_auth, "CUBE_API_BASE_URL", "https://api.example.com")
    dialog = CubeLoginDialog(None, "en")
    dialog.show()
    try:
        dialog._start_cooldown(20)
        dialog._show_step1()

        assert dialog.step1.isVisible() is True
        assert dialog.step2.isVisible() is False
        assert dialog._cooldown_timer.isActive() is False
    finally:
        dialog.deleteLater()
