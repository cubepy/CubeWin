#!/usr/bin/env bash
# Fetch Xray and sing-box for macOS or Linux.
#
# This is a DEVELOPMENT convenience, not part of a release. It exists so the
# app can be run from source on a Mac while the platform layer is worked on.
#
# It does not fetch a packet-interception driver, because there is no macOS
# equivalent of WinDivert — see docs/macos-port.md. The app will start and the
# spoofing core will report that it cannot run on this platform.
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
  curl -fsSL -o "$tmp/xray.zip" \
    "https://github.com/XTLS/Xray-core/releases/latest/download/$XRAY_ASSET"
  unzip -q "$tmp/xray.zip" -d "$tmp"
  for name in xray geoip.dat geosite.dat LICENSE; do
    [ -f "$tmp/$name" ] && cp "$tmp/$name" "$BIN/"
  done
  chmod +x "$BIN/xray"
  rm -rf "$tmp"
fi
"$BIN/xray" version | head -1

# --- sing-box ---------------------------------------------------------------
SING_VERSION=1.13.14
if [ ! -x "$BIN/sing-box" ]; then
  SING_ASSET="sing-box-$SING_VERSION-$OS-$ARCH"
  echo "Downloading $SING_ASSET..."
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/sing-box.tar.gz" \
    "https://github.com/SagerNet/sing-box/releases/download/v$SING_VERSION/$SING_ASSET.tar.gz"
  # NOT checksum-pinned, unlike the Windows x64 path in install-engine.ps1.
  # Pin it before this script is ever used for anything shipped.
  tar -xzf "$tmp/sing-box.tar.gz" -C "$tmp"
  cp "$tmp/$SING_ASSET/sing-box" "$BIN/sing-box"
  cp "$tmp/$SING_ASSET/LICENSE" "$BIN/sing-box-LICENSE" 2>/dev/null || true
  chmod +x "$BIN/sing-box"
  rm -rf "$tmp"
fi
"$BIN/sing-box" version | head -1

echo
echo "Engine binaries are in $BIN."
echo "Note: the spoofing core is Windows-only. Running the app here gives you"
echo "the interface and everything around it, not a working tunnel."
