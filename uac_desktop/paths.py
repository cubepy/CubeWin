from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def data_dir(os_name: str | None = None, platform_name: str | None = None,
             environ: "dict[str, str] | None" = None,
             home: Path | None = None) -> Path:
    """Where this platform expects an app to keep its per-user state.

    %APPDATA% does not exist off Windows, so the old fallback dropped settings
    into a bare ~/CubeVPN. Each platform has a convention; using it means a
    developer's files land where they belong instead of in their home root.

    The platform is a parameter so tests can ask about a platform they are not
    running on. Patching os.name globally would change how pathlib itself
    behaves.
    """
    os_name = os.name if os_name is None else os_name
    platform_name = sys.platform if platform_name is None else platform_name
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home

    override = environ.get("CUBEVPN_DATA_DIR")
    if override:
        return Path(override)
    if os_name == "nt":
        return Path(environ.get("APPDATA") or home) / "CubeVPN"
    if platform_name == "darwin":
        return home / "Library" / "Application Support" / "CubeVPN"
    return Path(environ.get("XDG_CONFIG_HOME") or home / ".config") / "CubeVPN"


ROOT = bundle_root()
ASSETS = ROOT / "assets"
BIN = ROOT / "bin"
DATA_DIR = data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "settings.json"
PROFILES_FILE = DATA_DIR / "profiles.json"
BOOKMARKS_FILE = DATA_DIR / "sni-bookmarks.json"
SNI_RESULTS_FILE = DATA_DIR / "sni-scan-results.json"
XRAY_CONFIG = DATA_DIR / "xray-config.json"
XRAY_OWNER_FILE = DATA_DIR / "xray-owner.json"
SING_BOX_CONFIG = DATA_DIR / "sing-box-tun.json"
SING_BOX_OWNER_FILE = DATA_DIR / "sing-box-owner.json"
LOG_FILE = DATA_DIR / "uac-spoofer.log"


def reveal(target, os_name: str | None = None,
           platform_name: str | None = None) -> None:
    """Open a file or folder in the platform's file manager.

    os.startfile only exists on Windows, so the two call sites that used it
    raised AttributeError anywhere else.
    """
    os_name = os.name if os_name is None else os_name
    platform_name = sys.platform if platform_name is None else platform_name
    if os_name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
        return
    opener = "open" if platform_name == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(target)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
