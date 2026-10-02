# Omarchy CPU Mode

An Omarchy bar widget for switching an Intel laptop between quiet operation
and full CPU performance.

The widget displays the active mode:

- **Q — Quiet:** power-saver profile, Turbo Boost disabled, Intel P-state
  capped at 60%.
- **F — Full:** balanced profile, Turbo Boost enabled, Intel P-state restored
  to 100%.

The selected mode is written to a systemd-tmpfiles policy so it persists
across reboots.

## Requirements

- Omarchy with the Omarchy Shell
- An Intel CPU using the `intel_pstate` driver
- `powerprofilesctl`
- `pkexec` and a graphical polkit authentication agent

## Install

```bash
git clone <repository-url> ~/Work/omarchy-cpu-mode
cd ~/Work/omarchy-cpu-mode
./install.sh
```

Click **Q** or **F** in the right side of the bar. Switching modes may display
a graphical authentication prompt.

## Command line

Check the current mode without elevated privileges:

```bash
omarchy-cpu-mode status
```

Switch modes:

```bash
pkexec omarchy-cpu-mode quiet
pkexec omarchy-cpu-mode full
pkexec omarchy-cpu-mode toggle
```

## Uninstall

```bash
./uninstall.sh
```

Uninstalling leaves the currently selected CPU policy in place. Switch to
Full mode before uninstalling if you want normal CPU performance restored.

## Safety

The plugin reduces heat by limiting CPU performance. It does not weaken the
system fan curve or prevent the fans from responding to high temperatures.

## License

MIT
