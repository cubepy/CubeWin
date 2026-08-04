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
