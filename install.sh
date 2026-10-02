#!/usr/bin/env bash
set -euo pipefail

readonly ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PLUGIN_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/local.cpu-mode"
readonly POLKIT_RULE="/etc/polkit-1/rules.d/49-omarchy-cpu-mode.rules"

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
sed "s/@USER@/$USER/g" "$ROOT_DIR/polkit/49-omarchy-cpu-mode.rules.in" |
  pkexec tee "$POLKIT_RULE" >/dev/null
pkexec chmod 0644 "$POLKIT_RULE"

omarchy plugin validate "$PLUGIN_DIR"
omarchy plugin enable local.cpu-mode --section right

echo "CPU Mode installed. Click Q/F in the Omarchy bar to toggle without a password."
