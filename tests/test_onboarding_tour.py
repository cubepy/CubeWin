from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import uac_desktop.storage as storage_module
from uac_desktop.storage import Storage
from uac_desktop.ui import STYLE, HelpDot, MainWindow, TutorialOverlay


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _redirect_storage(monkeypatch, tmp_path):
    for name in ("SETTINGS_FILE", "PROFILES_FILE",
                 "BOOKMARKS_FILE", "SNI_RESULTS_FILE"):
        monkeypatch.setattr(
            storage_module, name, tmp_path / f"{name.lower()}.json")


def _window(qapp, monkeypatch, tmp_path):
    _redirect_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(MainWindow, "_setup_tray", lambda self: None)
    monkeypatch.setattr(MainWindow, "refresh_processes", lambda self: None)
    monkeypatch.setattr(
        MainWindow, "check_for_updates", lambda self, manual=False: None)
    qapp.setStyleSheet(STYLE)
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qapp.processEvents()
    return window


def test_fresh_install_is_flagged_for_the_tour_and_upgrades_are_not(
        tmp_path, monkeypatch):
    _redirect_storage(monkeypatch, tmp_path)
    # No settings file on disk: a genuinely new install, so the tour is pending.
    assert Storage().settings["tutorial_seen"] is False

    # An existing settings file predates the feature; that user has already
    # learned the app and must not be interrupted on upgrade.
    monkeypatch.setattr(
        storage_module, "SETTINGS_FILE", tmp_path / "existing.json")
    (tmp_path / "existing.json").write_text('{"proxy_mode": true}')
    assert Storage().settings["tutorial_seen"] is True


def test_tour_walks_forward_and_back_over_every_step(
        qapp, tmp_path, monkeypatch):
    window = _window(qapp, monkeypatch, tmp_path)
    try:
        window.start_tutorial()
        qapp.processEvents()
        overlay = window._tutorial_overlay
        assert overlay.isVisible()
        total = len(overlay._steps)
        assert total >= 5

        seen_titles = []
        for index in range(total):
            assert overlay._index == index
            qapp.processEvents()
            overlay._sync_geometry()
            seen_titles.append(overlay.title_label.text())
            # Every step must anchor to a real, on-screen widget.
            assert not overlay._target_rect.isEmpty(), f"step {index}"
            assert overlay.card.geometry().left() >= 0
            assert overlay.card.geometry().right() <= overlay.width()
            assert overlay.card.geometry().top() >= 0
            assert overlay.card.geometry().bottom() <= overlay.height()
            if index < total - 1:
                overlay.next()
                qapp.processEvents()

        assert len(set(seen_titles)) == total
        assert overlay.back_button.isVisible()
        overlay.previous()
        assert overlay._index == total - 2
    finally:
        window._force_quit = True
        window.close()


def test_finishing_the_tour_records_it_and_hides_the_overlay(
        qapp, tmp_path, monkeypatch):
    window = _window(qapp, monkeypatch, tmp_path)
    try:
        window.storage.settings["tutorial_seen"] = False
        window.start_tutorial()
        qapp.processEvents()
        overlay = window._tutorial_overlay
        for _ in range(len(overlay._steps)):
            overlay.next()
            qapp.processEvents()
        assert not overlay.isVisible()
        assert window.storage.settings["tutorial_seen"] is True
    finally:
        window._force_quit = True
        window.close()


def test_escape_skips_the_tour_without_finishing_it(
        qapp, tmp_path, monkeypatch):
    window = _window(qapp, monkeypatch, tmp_path)
    try:
        window.storage.settings["tutorial_seen"] = False
        window.start_tutorial()
        qapp.processEvents()
        overlay = window._tutorial_overlay
        outcomes = []
        overlay.finished.connect(outcomes.append)
        overlay.keyPressEvent(_key_event(Qt.Key_Escape))
        qapp.processEvents()
        assert not overlay.isVisible()
        assert outcomes == [False]
        # Skipping still counts as answered; it must not reappear next launch.
        assert window.storage.settings["tutorial_seen"] is True
    finally:
        window._force_quit = True
        window.close()


def _key_event(key):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    return QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)


def test_tour_text_and_help_dots_follow_the_language_switch(
        qapp, tmp_path, monkeypatch):
    window = _window(qapp, monkeypatch, tmp_path)
    try:
        window.start_tutorial()
        qapp.processEvents()
        overlay = window._tutorial_overlay
        persian_title = overlay.title_label.text()
        persian_next = overlay.next_button.text()

        dots = [d for d in window.findChildren(HelpDot)
                if d.property("helpFa") is not None]
        assert len(dots) == window.stack.count(), "one page help dot per page"
        persian_tip = dots[0].toolTip()

        window.language = "fa"
        window.toggle_language()
        qapp.processEvents()
        assert window.language == "en"
        assert overlay.title_label.text() != persian_title
        assert overlay.next_button.text() != persian_next
        assert overlay.next_button.text() in {"Next", "Finish"}
        assert overlay.layoutDirection() == Qt.LeftToRight
        assert dots[0].toolTip() != persian_tip
        assert dots[0].property("helpEn") in dots[0].accessibleDescription()
    finally:
        window._force_quit = True
        window.close()


def test_every_tour_step_targets_a_widget_that_exists(
        qapp, tmp_path, monkeypatch):
    window = _window(qapp, monkeypatch, tmp_path)
    try:
        for step in window._tutorial_steps():
            step["show_page"]()
            qapp.processEvents()
            widget = step["target"]()
            assert widget is not None
            assert widget.isVisible()
            for key in ("title_fa", "title_en", "body_fa", "body_en"):
                assert step[key].strip(), key
    finally:
        window._force_quit = True
        window.close()


def test_card_stays_on_screen_and_never_covers_its_target(
        qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QRectF

    window = _window(qapp, monkeypatch, tmp_path)
    try:
        for width, height in ((1080, 700), (1280, 800), (1440, 900), (1920, 1080)):
            window.resize(width, height)
            qapp.processEvents()
            window.start_tutorial()
            qapp.processEvents()
            overlay = window._tutorial_overlay
            for index in range(len(overlay._steps)):
                qapp.processEvents()
                overlay._sync_geometry()
                card = overlay.card.geometry()
                where = f"{width}x{height} step {index}"
                assert card.left() >= 0 and card.top() >= 0, where
                assert card.right() <= overlay.width(), where
                assert card.bottom() <= overlay.height(), where
                # A card sitting on top of the widget it explains is useless.
                assert not QRectF(card).intersects(overlay._target_rect), where
                if index < len(overlay._steps) - 1:
                    overlay.next()
            overlay.skip()
            qapp.processEvents()
    finally:
        window._force_quit = True
        window.close()


def test_overlay_with_no_usable_steps_finishes_instead_of_hanging(qapp):
    from PySide6.QtWidgets import QWidget
    host = QWidget()
    host.resize(600, 400)
    overlay = TutorialOverlay(host)
    outcomes = []
    overlay.finished.connect(outcomes.append)
    overlay.start([], "fa")
    assert not overlay.isVisible()
    assert outcomes == [False]
