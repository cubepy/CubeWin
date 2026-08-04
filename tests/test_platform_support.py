from __future__ import annotations

import uac_desktop.platform_support as ps


def _fake_api(monkeypatch, machine_code):
    monkeypatch.setattr(ps, "_native_machine_from_api", lambda: machine_code)


def test_x64_host_is_supported(monkeypatch):
    monkeypatch.setattr(ps.os, "name", "nt")
    _fake_api(monkeypatch, ps.IMAGE_FILE_MACHINE_AMD64)
    monkeypatch.setattr(ps, "_process_architecture", lambda: "x64")

    host = ps.detect()
    assert host.native == "x64"
    assert host.supported
    assert not host.emulated
    assert ps.unsupported_message(host) == ("", "")


def test_arm64_host_running_the_x64_build_is_reported_as_emulated(monkeypatch):
    monkeypatch.setattr(ps.os, "name", "nt")
    # This is the case platform.machine() cannot see on its own: the process
    # believes it is x64 while the machine underneath is ARM64.
    _fake_api(monkeypatch, ps.IMAGE_FILE_MACHINE_ARM64)
    monkeypatch.setattr(ps, "_process_architecture", lambda: "x64")

    host = ps.detect()
    assert host.native == "ARM64"
    assert host.process == "x64"
    assert host.emulated
    assert not host.supported
    assert host.reason == "unsupported-arm64"
    assert "emulation" in host.label

    persian, english = ps.unsupported_message(host)
    assert "ARM64" in english
    assert "ARM64" in persian
    # The message has to name the actual mechanism, not just say "unsupported".
    assert "kernel" in english.lower()


def test_32_bit_windows_is_reported_as_unsupported(monkeypatch):
    monkeypatch.setattr(ps.os, "name", "nt")
    _fake_api(monkeypatch, ps.IMAGE_FILE_MACHINE_I386)
    monkeypatch.setattr(ps, "_process_architecture", lambda: "x86")

    host = ps.detect()
    assert host.reason == "unsupported-x86"
    assert not host.supported
    _persian, english = ps.unsupported_message(host)
    assert "32-bit" in english


def test_non_windows_host_is_reported_with_its_own_reason(monkeypatch):
    monkeypatch.setattr(ps.os, "name", "posix")
    _fake_api(monkeypatch, None)
    monkeypatch.setattr(ps, "_process_architecture", lambda: "x64")

    host = ps.detect()
    assert host.reason == "not-windows"
    assert not host.supported
    _persian, english = ps.unsupported_message(host)
    assert "Windows only" in english


def test_unrecognised_machine_is_allowed_through(monkeypatch):
    """A guess must never lock someone out of a machine that would work."""
    monkeypatch.setattr(ps.os, "name", "nt")
    _fake_api(monkeypatch, 0x1234)
    monkeypatch.setattr(ps, "_process_architecture", lambda: "unknown")
    monkeypatch.setattr(ps.os, "environ", {})
    monkeypatch.setattr(ps.platform, "machine", lambda: "SOMETHING-NEW")

    host = ps.detect()
    assert host.native == "unknown"
    assert host.supported


def test_environment_fallback_reads_the_native_architecture(monkeypatch):
    monkeypatch.setattr(ps.os, "name", "nt")
    _fake_api(monkeypatch, None)
    # WOW64 exposes the machine's real architecture here while
    # PROCESSOR_ARCHITECTURE describes the emulated process.
    monkeypatch.setattr(ps.os, "environ", {
        "PROCESSOR_ARCHITEW6432": "ARM64",
        "PROCESSOR_ARCHITECTURE": "AMD64",
    })
    monkeypatch.setattr(ps, "_process_architecture", lambda: "x64")

    host = ps.detect()
    assert host.native == "ARM64"
    assert not host.supported
