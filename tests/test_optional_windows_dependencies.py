from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Refuses to import pydivert, whatever is installed in this environment. The
# bug this guards against was invisible locally precisely because pydivert
# happened to be present.
_BLOCK_PYDIVERT = textwrap.dedent("""
    import sys
    class _Block:
        def find_module(self, name, path=None):
            if name == "pydivert" or name.startswith("pydivert."):
                return self
        def load_module(self, name):
            raise ImportError(f"No module named '{name}'")
    sys.meta_path.insert(0, _Block())
""")


def _run_without_pydivert(body: str, tmp_path: Path):
    # Inherit the environment; replacing it wholesale also cost the subprocess
    # its access to installed packages.
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["CUBEVPN_DATA_DIR"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_PYDIVERT + textwrap.dedent(body)],
        cwd=str(ROOT), capture_output=True, text=True, env=env,
    )


def test_requirements_marks_pydivert_as_windows_only():
    """Without the marker, `pip install -r requirements.txt` fails on macOS.

    pydivert is a WinDivert binding and has no purpose off Windows, but an
    unmarked pin aborted the whole install before any other dependency was
    fetched.
    """
    requirements = (ROOT / "requirements.txt").read_text()
    line = next(l for l in requirements.splitlines()
                if l.strip().startswith("pydivert"))
    assert 'sys_platform == "win32"' in line, line


def test_the_app_imports_without_pydivert(tmp_path):
    result = _run_without_pydivert("""
        import uac_desktop.engine
        import uac_desktop.pattern_core.core
        import uac_desktop.ui
        import main
        print("imported")
    """, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "imported" in result.stdout


def test_the_core_refuses_clearly_instead_of_raising_an_import_error(tmp_path):
    """Absent pydivert must surface as the platform message, not a stack trace."""
    result = _run_without_pydivert("""
        from uac_desktop.pattern_core.core import PatternSniCore
        from uac_desktop.models import ProxyProfile, Tuning
        try:
            PatternSniCore(lambda m: None).start(ProxyProfile(), Tuning())
        except RuntimeError as exc:
            print("REFUSED:", exc)
    """, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "REFUSED:" in result.stdout
    assert "WinDivert" in result.stdout


def test_requirements_avoids_the_pyside6_addons_download():
    """The meta-package drags in 316 MB of Qt this app never imports.

    On a slow or unreliable link that download is the most likely point of
    failure in the whole install, and it buys nothing.
    """
    requirements = (ROOT / "requirements.txt").read_text()
    lines = [l.strip() for l in requirements.splitlines()
             if l.strip() and not l.strip().startswith("#")]
    assert any(l.startswith("PySide6-Essentials") for l in lines), lines
    assert not any(l.startswith("PySide6>") or l == "PySide6" for l in lines), lines


def test_only_essentials_qt_modules_are_imported():
    """Guards the line above: importing from Addons would silently break it."""
    import re
    essentials = {"QtCore", "QtGui", "QtWidgets", "QtSvg", "QtSvgWidgets",
                  "QtNetwork", "QtXml", "QtSql", "QtTest", "QtPrintSupport",
                  "QtConcurrent", "QtQml", "QtQuick", "QtOpenGL", "QtUiTools"}
    used = set()
    for path in ROOT.rglob("*.py"):
        if ".git" in path.parts:
            continue
        used |= set(re.findall(r"from PySide6\.(\w+)", path.read_text(encoding="utf-8")))
    assert used, "no PySide6 imports found — the check would be vacuous"
    assert used <= essentials, f"needs PySide6-Addons: {sorted(used - essentials)}"


def test_a_non_executable_engine_binary_says_how_to_fix_it(tmp_path, monkeypatch):
    """An interrupted install leaves the binary copied but not chmod'd.

    subprocess then raises a bare "[Errno 13] Permission denied" naming
    nothing the user can act on, which is exactly what a macOS tester hit.
    """
    import uac_desktop.engine as engine_module

    binary = tmp_path / ("xray.exe" if os.name == "nt" else "xray")
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o644)
    monkeypatch.setattr(engine_module, "BIN", tmp_path)

    engine = engine_module.Engine.__new__(engine_module.Engine)
    with __import__("pytest").raises(PermissionError) as caught:
        engine._binary()

    message = str(caught.value)
    assert "cannot be executed" in message
    assert "chmod +x" in message, "the message has to carry the fix"
    assert str(binary) in message


def test_an_executable_binary_is_returned(tmp_path, monkeypatch):
    import uac_desktop.engine as engine_module

    binary = tmp_path / ("xray.exe" if os.name == "nt" else "xray")
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setattr(engine_module, "BIN", tmp_path)

    engine = engine_module.Engine.__new__(engine_module.Engine)
    assert engine._binary() == binary


def test_a_missing_binary_still_points_at_both_installers(tmp_path, monkeypatch):
    import uac_desktop.engine as engine_module

    monkeypatch.setattr(engine_module, "BIN", tmp_path)
    engine = engine_module.Engine.__new__(engine_module.Engine)
    with __import__("pytest").raises(FileNotFoundError) as caught:
        engine._binary()
    assert "install-engine.sh" in str(caught.value)
