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

command -v python3 >/dev/null || {
  echo "Python 3 is required to read CPU metrics." >&2
  exit 1
}

mkdir -p "$PLUGIN_DIR"
if [[ ! "$ROOT_DIR" -ef "$PLUGIN_DIR" ]]; then
  install -m 0644 "$ROOT_DIR/manifest.json" "$PLUGIN_DIR/manifest.json"
  install -m 0644 "$ROOT_DIR/cpu-metrics.py" "$PLUGIN_DIR/cpu-metrics.py"
  install -m 0644 "$ROOT_DIR/BarWidget.qml" "$PLUGIN_DIR/BarWidget.qml"
fi
pkexec install -o root -g root -m 0755 \
  "$ROOT_DIR/bin/omarchy-cpu-mode" \
  /usr/local/bin/omarchy-cpu-mode
sed "s/@USER@/$USER/g" "$ROOT_DIR/polkit/49-omarchy-cpu-mode.rules.in" |
  pkexec tee "$POLKIT_RULE" >/dev/null
pkexec chmod 0644 "$POLKIT_RULE"

omarchy plugin validate "$PLUGIN_DIR"
omarchy plugin enable local.cpu-mode --section right

echo "CPU Mode installed. Left-click Q/F to toggle; hover for metrics or right-click to pin them."
