# Omarchy CPU Mode

**A quieter laptop, one click away. Live CPU insights, one hover away.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Omarchy Shell](https://img.shields.io/badge/Omarchy-Shell-black.svg)](https://omarchy.org/)
[![GitHub](https://img.shields.io/badge/GitHub-alexpomsft%2Fomarchy--cpu--mode-181717.svg)](https://github.com/alexpomsft/omarchy-cpu-mode)

A small Omarchy Shell bar widget that switches an Intel CPU between **Quiet**
and **Full** modes. The bar stays uncluttered: a single **Q** or **F**, with a
compact live metrics popup when you want more detail.

## At a glance

| Interaction | What happens |
| --- | --- |
| Left-click Q/F | Toggle Quiet and Full modes |
| Hover briefly | Open the live metrics popup |
| Right-click | Pin the popup open |
| Right-click again or click outside | Close a pinned popup |

Move the pointer into a hover popup to keep it open. Metrics refresh every
two seconds while the popup is open; there is no background metrics polling
when it is closed.

Illustrative popup; readings and sensor labels depend on your hardware:

```text
CPU / Quiet

CPU temperature          49.0 C
CPU usage                 12.4%
CPU clock (average)     1.20 GHz
applesmc: fan1         2,170 RPM
applesmc: fan2         2,000 RPM
Turbo Boost            Disabled
Performance cap             60%
```

## Two simple modes

| Mode | Power profile | Turbo Boost | Intel P-state limit |
| --- | --- | --- | --- |
| **Q - Quiet** | `power-saver` | Disabled | 60% |
| **F - Full** | `balanced` | Enabled | 100% |

Full removes this plugin's CPU performance restrictions; it deliberately
uses the balanced power profile, not the performance profile. The Intel
P-state settings are saved in a systemd-tmpfiles policy and restored at boot.

**This is not a fan controller.** It reduces CPU performance in Quiet mode
without changing fan curves, firmware thermal protections, or fan targets.

## Requirements and compatibility

- Omarchy with the Quickshell-based **Omarchy Shell** and its plugin commands.
- An Intel CPU using the **`intel_pstate`** driver, exposing `no_turbo` and
  `max_perf_pct`. CPU mode switching is not supported on AMD or other drivers.
- **`powerprofilesctl`**, with its power-profiles service running.
- **`pkexec`** and a graphical polkit authentication agent.
- **Python 3**, standard library only.
- Readable Linux hwmon or CPU thermal-zone sensors for hardware readings.

Intel/Apple SMC hardware has been exercised on a MacBookPro15,1. The reader
supports modern hwmon attributes and the older `hwmon*/device` layout used
by Apple SMC; it does not install or configure hardware drivers.

No `lm-sensors`, network access, or elevated privileges are needed to collect
metrics. Omarchy plugins themselves run unsandboxed with your user permissions.
Review the source before installing.

## Install

**One manual setup step is required.** Omarchy's plugin installer clones the
widget, but does not run its privileged helper setup automatically.

```bash
omarchy plugin add https://github.com/alexpomsft/omarchy-cpu-mode.git
"${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/local.cpu-mode/install.sh"
```

Review the source before running `install.sh`. The script installs the
root-owned CPU helper, adds a user-scoped polkit rule, and enables the widget
on the right side of the bar. Installation may show authentication prompts;
subsequent mode switches do not.

Alternatively, install from a separate source checkout:

```bash
git clone https://github.com/alexpomsft/omarchy-cpu-mode.git
cd omarchy-cpu-mode
./install.sh
```

The stable plugin ID is **`local.cpu-mode`**. Move it with:

```bash
omarchy bar move local.cpu-mode --section right
```

## What the popup measures

| Metric | Source and behavior |
| --- | --- |
| CPU temperature | Hottest CPU package reading; falls back to CPU cores or CPU thermal zones |
| CPU usage | Short sample of aggregate `/proc/stat` counters |
| CPU clock | Average current frequency across available CPU frequency policies |
| Fan speeds | All hwmon fan RPM inputs, with device labels or fan numbers |
| Turbo Boost | Intel P-state `no_turbo` state |
| Performance cap | Intel P-state `max_perf_pct` |

GPU, SSD, and battery temperatures are not presented as CPU temperature.
A fan stopped at zero RPM is shown as **0 RPM**, not mistaken for a missing
sensor. Firmware that does not expose fan readings shows **Not exposed**;
other unsupported or unreadable metrics show **Unavailable**. Read failures
are indicated in the popup and logged by the shell.

## Update

For an Omarchy-managed Git checkout:

```bash
omarchy plugin update local.cpu-mode
"${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/local.cpu-mode/install.sh"
```

Re-running setup also updates the root-owned helper. For a separate source
checkout, use `git pull --ff-only` and run `./install.sh` again instead.

## Command line

Check the current mode without root access:

```bash
omarchy-cpu-mode status
```

Switch modes using the same helper as the widget:

```bash
pkexec omarchy-cpu-mode quiet
pkexec omarchy-cpu-mode full
pkexec omarchy-cpu-mode toggle
```

Read the popup's metrics as JSON from the installed plugin:

```bash
python3 "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/local.cpu-mode/cpu-metrics.py"
```

## Uninstall

If you want to restore the plugin's Full settings first:

```bash
pkexec omarchy-cpu-mode full
```

Then remove the widget and its privileged setup:

```bash
"${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/local.cpu-mode/uninstall.sh"
```

For an installation copied from a separate checkout, run `./uninstall.sh`
from that checkout instead. Using only `omarchy plugin remove` does not remove
the privileged helper or polkit rule.

Uninstall deliberately leaves the selected CPU policy in place, including
its boot-time policy file. Switch to Full first if you do not want to retain
Quiet's CPU limits.

## Permissions and system changes

Metrics only read `/proc` and `/sys`. Mode changes use a fixed-command,
root-owned Bash helper; the plugin never modifies fan settings.

| Path | Purpose |
| --- | --- |
| `~/.config/omarchy/plugins/local.cpu-mode/` | User-owned widget files and bar registration; honors `XDG_CONFIG_HOME` |
| `/usr/local/bin/omarchy-cpu-mode` | Root-owned mode-switching helper |
| `/etc/polkit-1/rules.d/49-omarchy-cpu-mode.rules` | Passwordless helper access for the installing, active local user |
| `/etc/tmpfiles.d/intel-pstate-cool.conf` | Persistent P-state settings, written when switching modes |

The polkit rule authorizes only this helper, not a general shell or
interpreter. Its accepted actions are `status`, `quiet`, `full`, and `toggle`.
The helper changes the power profile and Intel P-state controls; it does not
disable system thermal protections.

## Development

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh uninstall.sh bin/omarchy-cpu-mode
omarchy plugin validate .
```

Sensor tests use temporary filesystem fixtures. Installer tests use mocked
Omarchy/polkit commands and do not perform privileged installation.

If saved widget changes do not show up, force plugin discovery:

```bash
omarchy-shell shell rescanPlugins
```

## License

[MIT](LICENSE).
