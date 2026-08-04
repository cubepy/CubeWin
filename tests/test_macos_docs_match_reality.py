"""The macOS docs made concrete claims that silently went stale.

Both documents were written before `select_sni_core()` gained the
fragmentation fallback, and both kept telling readers the tunnel does not work
on macOS long after it did. The Persian one is the only document this
project's user can read, so a wrong claim there is not a cosmetic problem.

These check the falsifiable claims only — ports, and the shape of the
platform split. Prose is not testable and is not tested.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PERSIAN = ROOT / "docs" / "macos-fa.md"
ENGLISH = ROOT / "docs" / "macos-port.md"


@pytest.fixture(scope="module")
def persian():
    return PERSIAN.read_text(encoding="utf-8")


def test_the_proxy_ports_the_guide_quotes_are_the_ones_the_app_opens(persian):
    """macOS users must set these by hand, so a stale number costs an evening."""
    from uac_desktop.engine import HTTP_PORT, SOCKS_PORT

    assert f"127.0.0.1:{SOCKS_PORT}" in persian
    assert f"127.0.0.1:{HTTP_PORT}" in persian


def test_neither_document_still_says_the_tunnel_is_broken(persian):
    english = " ".join(ENGLISH.read_text(encoding="utf-8").split())
    assert "اتصال (تونل) | ❌" not in persian
    assert "cannot connect is worse than no macOS build" in english, (
        "the warning against shipping a dead build should survive; "
        "it is the claim *about today* that had to change"
    )


def test_the_guide_names_the_core_that_actually_runs_there(persian, monkeypatch):
    """`SNI core: fragmentation` is what the log prints; the doc quotes it."""
    import uac_desktop.engine as engine_module
    import uac_desktop.platform_support as ps

    host = ps.HostArchitecture(
        native="arm64", process="arm64", emulated=False,
        supported=False, reason="not-windows",
    )
    monkeypatch.setattr(engine_module, "detect_host", lambda: host)
    core = engine_module.select_sni_core(lambda _m: None)
    assert "fragmentation" in getattr(core, "selection_label", "")
    assert "fragmentation" in persian


def test_the_windows_only_features_the_guide_lists_are_the_disabled_ones(persian):
    """Three controls, named the same way in the doc and in the UI."""
    for feature in ("پروکسی سیستم", "حالت TUN", "درگاه موبایل"):
        assert feature in persian, feature


def test_the_gatekeeper_fix_is_written_down(persian):
    """The one failure a macOS tester cannot possibly guess at."""
    assert "xattr -cr" in persian
