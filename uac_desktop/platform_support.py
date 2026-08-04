"""Host architecture detection.

The spoofing core runs on WinDivert, which is a Windows *kernel driver*. Kernel
drivers are never emulated: on an ARM64 PC, Windows happily runs this x64 build
in user mode — the window opens, the UI works — and then the driver refuses to
load with an error that says nothing about why. This module names the real
reason so the app can say it out loud instead of leaving the user guessing.

`platform.machine()` cannot answer this on its own: inside an emulated x64
process it reports "AMD64", the emulated architecture, not the machine's. The
native architecture comes from IsWow64Process2, which reports both.
"""

from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import dataclass

# Values from winnt.h. IsWow64Process2 reports the native machine as one of
# these regardless of what the current process is being emulated as.
IMAGE_FILE_MACHINE_UNKNOWN = 0x0000
IMAGE_FILE_MACHINE_I386 = 0x014C
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_ARM64 = 0xAA64
IMAGE_FILE_MACHINE_ARMNT = 0x01C4

_MACHINE_NAMES = {
    IMAGE_FILE_MACHINE_I386: "x86",
    IMAGE_FILE_MACHINE_AMD64: "x64",
    IMAGE_FILE_MACHINE_ARM64: "ARM64",
    IMAGE_FILE_MACHINE_ARMNT: "ARM32",
}

# The one architecture this build ships a matching WinDivert driver for.
SUPPORTED = "x64"


@dataclass(frozen=True)
class HostArchitecture:
    """What the machine actually is, and whether this build can drive it."""

    native: str            # "x64" / "ARM64" / "x86" / "unknown"
    process: str           # what this process is running as
    emulated: bool         # process architecture differs from the machine's
    supported: bool
    reason: str            # "" when supported, else a short machine-readable tag

    @property
    def label(self) -> str:
        if self.emulated:
            return f"{self.native} (running {self.process} under emulation)"
        return self.native


def _native_machine_from_api() -> int | None:
    """Ask Windows for the machine's real architecture.

    IsWow64Process2 exists on Windows 10 1511 and later. Anything older cannot
    be an ARM64 device, so falling through to the environment is safe there.
    """
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.windll.kernel32
        is_wow64_process2 = kernel32.IsWow64Process2
    except (AttributeError, OSError):
        return None
    process_machine = ctypes.c_uint16(0)
    native_machine = ctypes.c_uint16(0)
    try:
        ok = is_wow64_process2(
            kernel32.GetCurrentProcess(),
            ctypes.byref(process_machine),
            ctypes.byref(native_machine),
        )
    except OSError:
        return None
    if not ok:
        return None
    return int(native_machine.value)


def _native_machine_from_environment() -> str:
    """Fallback for pre-1511 Windows and for non-Windows hosts."""
    for name in ("PROCESSOR_ARCHITEW6432", "PROCESSOR_ARCHITECTURE"):
        value = str(os.environ.get(name, "")).strip().upper()
        if value in ("AMD64", "X64"):
            return "x64"
        if value in ("ARM64", "AARCH64"):
            return "ARM64"
        if value in ("X86", "I386", "I686"):
            return "x86"
    machine = str(platform.machine() or "").strip().upper()
    if machine in ("AMD64", "X86_64", "X64"):
        return "x64"
    if machine in ("ARM64", "AARCH64"):
        return "ARM64"
    if machine in ("X86", "I386", "I686"):
        return "x86"
    return "unknown"


def _process_architecture() -> str:
    machine = str(platform.machine() or "").strip().upper()
    if machine in ("AMD64", "X86_64", "X64"):
        return "x64"
    if machine in ("ARM64", "AARCH64"):
        return "ARM64"
    if machine in ("X86", "I386", "I686"):
        return "x86"
    return "unknown"


def detect() -> HostArchitecture:
    native_code = _native_machine_from_api()
    if native_code is not None and native_code != IMAGE_FILE_MACHINE_UNKNOWN:
        native = _MACHINE_NAMES.get(native_code, "unknown")
    else:
        native = _native_machine_from_environment()
    process = _process_architecture()
    emulated = native != process and "unknown" not in (native, process)

    if os.name != "nt":
        reason = "not-windows"
    elif native == SUPPORTED:
        reason = ""
    elif native == "unknown":
        # Never block on a guess: an unrecognised machine is allowed through
        # and will fail later with the driver's own error if it truly cannot
        # run. A false positive here would lock out a working PC.
        reason = ""
    else:
        reason = f"unsupported-{native.lower()}"

    return HostArchitecture(
        native=native, process=process, emulated=emulated,
        supported=not reason, reason=reason,
    )


def unsupported_message(host: HostArchitecture) -> tuple[str, str]:
    """Bilingual (Persian, English) explanation for an unsupported machine."""
    if host.supported:
        return ("", "")
    if host.reason == "not-windows":
        return (
            "این نسخه فقط روی ویندوز اجرا می‌شود. هسته اسپوف به درایور WinDivert"
            " نیاز دارد که یک درایور کرنل ویندوز است و معادلی روی این سیستم‌عامل"
            " ندارد.",
            "This build runs on Windows only. The spoofing core needs the"
            " WinDivert driver, which is a Windows kernel driver with no"
            " equivalent on this operating system.",
        )
    if host.reason == "unsupported-arm64":
        return (
            "این نسخه برای ویندوز x64 ساخته شده و روی پردازنده ARM64 کار نمی‌کند."
            " ویندوز بخش‌های عادی برنامه را شبیه‌سازی می‌کند، ولی درایور کرنل"
            " شبیه‌سازی نمی‌شود؛ بنابراین رابط باز می‌شود اما اتصال برقرار"
            " نخواهد شد. نسخه ARM64 هنوز منتشر نشده است.",
            "This is the Windows x64 build and it cannot drive an ARM64 CPU."
            " Windows emulates the ordinary parts of the app, but kernel"
            " drivers are never emulated — so the window opens while the"
            " connection can never come up. An ARM64 build is not released"
            " yet.",
        )
    if host.reason == "unsupported-x86":
        return (
            "این نسخه ۶۴ بیتی است و روی ویندوز ۳۲ بیتی اجرا نمی‌شود. نسخه ۳۲"
            " بیتی وجود ندارد، چون کتابخانه رابط کاربری (Qt6) دیگر از ویندوز ۳۲"
            " بیتی پشتیبانی نمی‌کند.",
            "This is the 64-bit build and it cannot run on 32-bit Windows."
            " There is no 32-bit build: the UI toolkit (Qt6) dropped 32-bit"
            " Windows support.",
        )
    return (
        f"معماری این دستگاه ({host.label}) پشتیبانی نمی‌شود. این نسخه فقط روی"
        " ویندوز x64 اجرا می‌شود.",
        f"This machine's architecture ({host.label}) is not supported. This"
        " build runs on Windows x64 only.",
    )
