#!/usr/bin/env bash
# Fetch Xray and sing-box for macOS or Linux.
#
# This is a DEVELOPMENT convenience, not part of a release. It exists so the
# app can be run from source on a Mac while the platform layer is worked on.
#
# It does not fetch a packet-interception driver, because there is no macOS
# equivalent of WinDivert — see docs/macos-port.md. The app falls back to TLS
# fragmentation instead, so the tunnel works; System Proxy, TUN Mode and
# Mobile Gateway do not, and appear disabled.
set -euo pipefail
cd "$(dirname "$0")"

BIN="$(pwd)/bin"
mkdir -p "$BIN"

case "$(uname -s)" in
  Darwin) OS=macos ;;
  Linux)  OS=linux ;;
  *) echo "Unsupported OS: $(uname -s). Use install-engine.ps1 on Windows." >&2; exit 1 ;;
esac

case "$(uname -m)" in
  arm64|aarch64) ARCH=arm64 ;;
  x86_64|amd64)  ARCH=amd64 ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

echo "Target: $OS-$ARCH"
XRAY_OK=1

# Downloads here routinely cross unreliable links — a partial transfer that
# aborts the script is the common failure, not a missing file. Retry, resume
# what already arrived, and be patient about a slow start.
download() {
  local url="$1" out="$2"
  curl -fL --retry 5 --retry-delay 3 --retry-all-errors \
       --connect-timeout 20 --speed-time 60 --speed-limit 1024 \
       -C - -o "$out" "$url"
}

# macOS tags anything curl downloads with com.apple.quarantine, and Gatekeeper
# then refuses to execute it. Without this the binary is present, executable,
# and still unusable.
unquarantine() {
  [ "$OS" = "macos" ] || return 0
  xattr -d com.apple.quarantine "$1" 2>/dev/null || true
  xattr -c "$1" 2>/dev/null || true
}

# --- Xray -------------------------------------------------------------------
if [ ! -x "$BIN/xray" ]; then
  case "$OS-$ARCH" in
    macos-arm64) XRAY_ASSET=Xray-macos-arm64-v8a.zip ;;
    macos-amd64) XRAY_ASSET=Xray-macos-64.zip ;;
    linux-arm64) XRAY_ASSET=Xray-linux-arm64-v8a.zip ;;
    linux-amd64) XRAY_ASSET=Xray-linux-64.zip ;;
  esac
  echo "Downloading $XRAY_ASSET..."
  tmp="$(mktemp -d)"
  download "https://github.com/XTLS/Xray-core/releases/latest/download/$XRAY_ASSET" \
           "$tmp/xray.zip"
  unzip -q "$tmp/xray.zip" -d "$tmp"
  for name in xray geoip.dat geosite.dat LICENSE; do
    [ -f "$tmp/$name" ] && cp "$tmp/$name" "$BIN/"
  done
  chmod +x "$BIN/xray"
  rm -rf "$tmp"
fi
chmod +x "$BIN/xray" 2>/dev/null || true
unquarantine "$BIN/xray"
if [ ! -x "$BIN/xray" ]; then
  echo "xray was downloaded but is not executable: $BIN/xray" >&2
  exit 1
fi
if ! "$BIN/xray" version 2>/dev/null | head -1; then
  echo "WARNING: $BIN/xray would not run. Continuing so the rest still installs." >&2
  XRAY_OK=0
fi

# --- sing-box ---------------------------------------------------------------
SING_VERSION=1.13.14
if [ ! -x "$BIN/sing-box" ]; then
  SING_ASSET="sing-box-$SING_VERSION-$OS-$ARCH"
  echo "Downloading $SING_ASSET..."
  tmp="$(mktemp -d)"
  download "https://github.com/SagerNet/sing-box/releases/download/v$SING_VERSION/$SING_ASSET.tar.gz" \
           "$tmp/sing-box.tar.gz"
  # NOT checksum-pinned, unlike the Windows x64 path in install-engine.ps1.
  # Pin it before this script is ever used for anything shipped.
  tar -xzf "$tmp/sing-box.tar.gz" -C "$tmp"
  cp "$tmp/$SING_ASSET/sing-box" "$BIN/sing-box"
  cp "$tmp/$SING_ASSET/LICENSE" "$BIN/sing-box-LICENSE" 2>/dev/null || true
  chmod +x "$BIN/sing-box"
  rm -rf "$tmp"
fi
chmod +x "$BIN/sing-box" 2>/dev/null || true
unquarantine "$BIN/sing-box"
if [ ! -x "$BIN/sing-box" ]; then
  echo "WARNING: $BIN/sing-box is not executable. TUN Mode will be unavailable." >&2
elif ! "$BIN/sing-box" version 2>/dev/null | head -1; then
  echo "WARNING: $BIN/sing-box would not run. TUN Mode will be unavailable." >&2
fi

echo
echo "Engine binaries are in $BIN."
echo "Note: WinDivert wrong-sequence injection is Windows-only, so this host"
echo "uses TLS fragmentation instead. The tunnel works; Windows System Proxy,"
echo "TUN Mode and Mobile Gateway do not, and appear disabled in the app."

if [ "$XRAY_OK" -ne 1 ]; then
  echo >&2
  echo "xray is installed but did not run. On macOS this is usually Gatekeeper:" >&2
  echo "  xattr -cr '$BIN'" >&2
  exit 1
fi
