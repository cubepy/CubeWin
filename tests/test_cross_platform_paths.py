from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import uac_desktop.paths as paths


def test_the_package_imports_without_windows_modules():
    """engine.py used to `import winreg` unconditionally.

    That single line meant the app could not even be imported on macOS, so no
    development was possible there at all.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import uac_desktop.engine, uac_desktop.gateway"],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("os_name, platform_name, expected_tail", [
    ("nt", "win32", ("Roaming", "CubeVPN")),
    ("posix", "darwin", ("Library", "Application Support", "CubeVPN")),
    ("posix", "linux", (".config", "CubeVPN")),
])
def test_each_platform_gets_its_own_convention(os_name, platform_name, expected_tail):
    home = Path("/home/tester")
    resolved = paths.data_dir(
        os_name=os_name, platform_name=platform_name,
        environ={"APPDATA": "/home/tester/AppData/Roaming"}, home=home,
    )
    assert resolved.parts[-len(expected_tail):] == expected_tail


def test_linux_honours_xdg_config_home():
    resolved = paths.data_dir(
        os_name="posix", platform_name="linux",
        environ={"XDG_CONFIG_HOME": "/home/tester/xdg"}, home=Path("/home/tester"),
    )
    assert resolved == Path("/home/tester/xdg/CubeVPN")


def test_windows_without_appdata_falls_back_to_home():
    resolved = paths.data_dir(
        os_name="nt", platform_name="win32", environ={}, home=Path("/home/tester"))
    assert resolved == Path("/home/tester/CubeVPN")


def test_explicit_override_wins_everywhere():
    for os_name, platform_name in (("nt", "win32"), ("posix", "darwin"), ("posix", "linux")):
        resolved = paths.data_dir(
            os_name=os_name, platform_name=platform_name,
            environ={"CUBEVPN_DATA_DIR": "/somewhere/else"}, home=Path("/home/tester"),
        )
        assert resolved == Path("/somewhere/else")


def test_reveal_uses_the_platform_opener(monkeypatch, tmp_path):
    """os.startfile does not exist off Windows; the two callers used to crash."""
    launched = []
    monkeypatch.setattr(paths.subprocess, "Popen",
                        lambda cmd, **kwargs: launched.append(cmd))

    paths.reveal(tmp_path, os_name="posix", platform_name="darwin")
    assert launched[-1][0] == "open"

    paths.reveal(tmp_path, os_name="posix", platform_name="linux")
    assert launched[-1][0] == "xdg-open"


def test_reveal_uses_startfile_on_windows(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(paths.os, "startfile", opened.append, raising=False)
    paths.reveal(tmp_path, os_name="nt", platform_name="win32")
    assert opened == [tmp_path]
