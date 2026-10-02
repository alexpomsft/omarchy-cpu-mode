#!/usr/bin/env bash
set -euo pipefail

readonly PLUGIN_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/local.cpu-mode"

if omarchy plugin list --json | grep -q '"id":"local.cpu-mode"'; then
  omarchy plugin disable local.cpu-mode
fi

rm -rf -- "$PLUGIN_DIR"
pkexec rm -f -- /usr/local/bin/omarchy-cpu-mode
pkexec rm -f -- /etc/polkit-1/rules.d/49-omarchy-cpu-mode.rules

echo "CPU Mode removed. The currently selected CPU policy was left unchanged."
