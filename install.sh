#!/usr/bin/env bash
# Cache Cleaner — one-command install for EndeavourOS / Arch Linux.
#
# Usage (from the cloned repository root):
#     ./install.sh
#
# Builds the native Arch package (cachecleaner-<ver>-any.pkg.tar.zst) and
# installs it with all dependencies. Requires: base-devel (makepkg), network.
set -euo pipefail

cd "$(dirname "$0")/packaging"

if ! command -v makepkg >/dev/null 2>&1; then
  echo "error: makepkg not found — this installer targets Arch/EndeavourOS" >&2
  exit 1
fi

makepkg -si

echo
echo "✔ Cache Cleaner installed. Launch 'Cache Cleaner' from your app menu,"
echo "  or run:  cachecleaner"
