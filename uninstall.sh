#!/usr/bin/env bash
# Cache Cleaner — complete removal for EndeavourOS / Arch Linux.
#
# Usage:
#     ./uninstall.sh
#
# What it removes:
#   1. the cachecleaner package (and the 'cache-cleaner' rename if present)
#   2. dependencies that NOTHING ELSE needs anymore (-Rns: recursive,
#      unneeded deps, config files). Shared libraries still required by
#      other apps (gtk4, libadwaita, python-gobject, …) are kept — pacman
#      decides that automatically; this script never force-removes them.
#   3. the app's private state (structured logs)
#
# It never touches your caches, documents or any other user data.
set -euo pipefail

removed_any=0
for pkg in cachecleaner cache-cleaner; do
  if pacman -Q "$pkg" >/dev/null 2>&1; then
    sudo pacman -Rns "$pkg"
    removed_any=1
  fi
done

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/cachecleaner"
if [ -e "$state_dir" ]; then
  rm -rf "$state_dir"
  echo "removed app state/logs: $state_dir"
fi

if [ "$removed_any" -eq 1 ]; then
  echo
  echo "✔ Cache Cleaner fully removed."
  echo "  Optional: delete the cloned sources, e.g.  rm -rf ~/Arch-cache-cleaner-with-GUI"
else
  echo "Cache Cleaner package not found — only state cleaned up (if present)."
fi
