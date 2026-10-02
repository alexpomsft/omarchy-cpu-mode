#!/usr/bin/env bash
set -euo pipefail

readonly ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PLUGIN_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/local.cpu-mode"

command -v omarchy >/dev/null || {
  echo "Omarchy is required." >&2
  exit 1
}

command -v pkexec >/dev/null || {
  echo "pkexec is required to install the privileged helper." >&2
  exit 1
}

mkdir -p "$PLUGIN_DIR"
install -m 0644 "$ROOT_DIR/manifest.json" "$PLUGIN_DIR/manifest.json"
install -m 0644 "$ROOT_DIR/BarWidget.qml" "$PLUGIN_DIR/BarWidget.qml"
pkexec install -o root -g root -m 0755 \
  "$ROOT_DIR/bin/omarchy-cpu-mode" \
  /usr/local/bin/omarchy-cpu-mode

omarchy plugin validate "$PLUGIN_DIR"
omarchy plugin enable local.cpu-mode --section right

echo "CPU Mode installed. Click Q/F in the Omarchy bar to toggle modes."
