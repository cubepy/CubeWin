# What a macOS port would actually take

> فارسی: [`macos-fa.md`](macos-fa.md)

This is a scoping document, not a plan of record. Nothing here is built.

The short version: **most of the app ports for free, and the part that does not
is the part the app exists for.** Packaging a macOS build is not the work;
replacing the packet-interception core is.

## What carries over unchanged

Measured against the current tree, by Windows-only API references
(`ctypes.windll`, `winreg`, `pydivert`, `os.startfile`, `.exe`):

| Module | Lines | Windows-only refs |
|---|---:|---:|
| `models.py` | 550 | 0 |
| `storage.py` | 489 | 0 |
| `fragment_proxy.py` | 508 | 0 |
| `network.py` | 377 | 0 |
| `update_checker.py` | 357 | 1 |
| `icons.py` | 278 | 0 |
| `cube_auth.py` | 181 | 0 |
| `tls_tools.py` | 107 | 0 |
| `verified_configs.py` | 81 | 0 |

That is roughly 2,900 lines — config parsing, storage, the account API, TLS
helpers, the update checker, the icon set — that need little or no change.

Qt runs natively on macOS and PySide6 ships a `macosx_13_0_universal2` wheel,
so the interface is portable too. `ui.py` is large but only touches Windows in
a handful of places (`os.startfile`, the tray, the elevation prompt).

## What has to be rebuilt

### 1. Packet interception — the real work

`pattern_core/core.py` is built on WinDivert: a Windows kernel driver that
sniffs and injects raw TCP. macOS has no equivalent you can simply swap in.

- Apple has effectively closed kernel extensions since macOS 11. New kexts need
  a special entitlement and are a dead end for a distributed app.
- The supported replacement is the **NetworkExtension** framework — a
  `NEPacketTunnelProvider` or a content filter running in a sandboxed system
  extension. It is a different architecture, not a different API: you get a
  virtual interface and a packet flow, not the ability to inject a forged
  segment onto an existing connection.
- Whether the wrong-sequence technique can be expressed at all through
  NetworkExtension is an **open question that has to be answered before any
  code is written.** If it cannot, the port has no core and the answer is a
  different circumvention method on macOS, not a port.

Distribution adds its own gate: shipping a NetworkExtension needs the
`com.apple.developer.networking.networkextension` entitlement, which is
requested from Apple separately, plus notarization.

### 2. System proxy

`engine.py` reads and writes `HKCU\...\Internet Settings` through `winreg`
(47 Windows-only references in that file alone). The macOS equivalent is
`networksetup -setwebproxy` / `scutil`, per network service — a different
model, and one that needs care to restore cleanly on crash, the same way
`WindowsProxy.recover_stale` does today.

### 3. Mobile Gateway

`gateway.py` uses `iphlpapi.SendARP` and Windows ICS. macOS has Internet
Sharing, driven very differently. This is the most self-contained piece and
the easiest to drop from a first macOS release.

### 4. Elevation and process control

`main.py` relaunches through `ShellExecuteW runas`; the engine controls child
processes with `kernel32` job objects. On macOS the equivalents are a
privileged helper installed via `SMJobBless` and ordinary POSIX process
handling.

### 5. Bundled binaries

Xray and sing-box both publish `darwin-arm64` and `darwin-amd64` builds, so
`install-engine.ps1` would need a shell counterpart. This part is easy.

## Order of work, if it were ever started

1. **Answer the core question first.** Prototype the wrong-sequence technique
   over NetworkExtension, outside this repo, and find out whether macOS permits
   it at all. Everything below is wasted effort until this is settled.
2. Split the platform layer out of `engine.py` behind an interface, so Windows
   and macOS implementations sit side by side. This is worth doing on its own
   merits even if macOS never happens — that file is 2,541 lines with the
   platform woven through it.
3. Port system proxy control.
4. Port packaging and the engine fetch script.
5. Mobile Gateway last, or never.

## Recommendation

Do not start with packaging. Start with step 1, as a throwaway prototype. The
entire port is contingent on it, it is the smallest piece to test, and if the
answer is no it saves the rest of the effort.

A macOS build that opens and cannot connect is worse than no macOS build: users
download it, it fails, and they conclude the project is broken.
