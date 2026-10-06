#!/usr/bin/env python3
"""Read CPU metrics without elevated privileges or external dependencies."""

import errno
import json
from pathlib import Path
import time


CPU_SENSOR_NAMES = {"coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal"}
CPU_THERMAL_TYPES = {"x86_pkg_temp", "cpu_thermal", "cpu-thermal"}


def read_text(path, errors, *, optional=False):
    try:
        return path.read_text().strip()
    except (OSError, UnicodeError) as error:
        # Apple SMC exposes optional label files that may return EINVAL.
        if optional and isinstance(error, OSError) and error.errno in (errno.ENOENT, errno.EINVAL):
            return None
        errors.append(f"{path}: {error}")
        return None


def read_int(path, errors):
    text = read_text(path, errors)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        errors.append(f"{path}: invalid integer {text!r}")
        return None


def cpu_counters(proc_root, errors):
    path = proc_root / "stat"
    text = read_text(path, errors)
    if text is None:
        return None
    fields = text.splitlines()[0].split() if text else []
    try:
        if len(fields) < 5 or fields[0] != "cpu":
            raise ValueError
        # Guest counters are already included in user/nice, so exclude them.
        values = [int(value) for value in fields[1:9]]
        if any(value < 0 for value in values):
            raise ValueError
    except ValueError:
        errors.append(f"{path}: invalid aggregate CPU counters")
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def cpu_usage(before, after, errors):
    if before is None or after is None:
        return None
    total = after[0] - before[0]
    idle = after[1] - before[1]
    if total <= 0 or idle < 0 or idle > total:
        errors.append("CPU usage: counters did not advance consistently")
        return None
    return round(100 * (total - idle) / total, 1)


def sensors(sys_root, errors):
    temperatures = []
    fans = []
    for device in sorted((sys_root / "class/hwmon").glob("hwmon*")):
        sensor_dir = device
        if not (device / "name").exists() and (device / "device/name").exists():
            sensor_dir = device / "device"
        name_path = sensor_dir / "name"
        name = read_text(name_path, errors) if name_path.exists() else device.name
        name = name or device.name
        if name in CPU_SENSOR_NAMES:
            preferred = []
            fallback = []
            for path in sorted(sensor_dir.glob("temp*_input")):
                value = read_int(path, errors)
                if value is None:
                    continue
                label_path = path.with_name(path.name.replace("_input", "_label"))
                label = read_text(label_path, errors, optional=True)
                label = (label or "").lower()
                target = preferred if label.startswith("package") or label == "tdie" else fallback
                target.append(value / 1000)
            temperatures.extend(preferred or fallback)

        for path in sorted(sensor_dir.glob("fan*_input")):
            rpm = read_int(path, errors)
            if rpm is not None and rpm < 0:
                errors.append(f"{path}: negative fan speed")
                rpm = None
            label_path = path.with_name(path.name.replace("_input", "_label"))
            label = read_text(label_path, errors, optional=True)
            fans.append({"label": f"{name}: {label or path.stem.replace('_input', '')}", "rpm": rpm})

    if not temperatures:
        for zone in sorted((sys_root / "class/thermal").glob("thermal_zone*")):
            sensor_type = read_text(zone / "type", errors)
            if sensor_type in CPU_THERMAL_TYPES:
                value = read_int(zone / "temp", errors)
                if value is not None:
                    temperatures.append(value / 1000)

    return max(temperatures) if temperatures else None, fans


def frequency(sys_root, errors):
    values = []
    for path in sorted((sys_root / "devices/system/cpu/cpufreq").glob("policy*/scaling_cur_freq")):
        value = read_int(path, errors)
        if value is not None:
            if value > 0:
                values.append(value / 1000)
            else:
                errors.append(f"{path}: non-positive CPU frequency")
    return round(sum(values) / len(values), 1) if values else None


def collect_metrics(sys_root=Path("/sys"), proc_root=Path("/proc"), sample_interval=0.2):
    errors = []
    before = cpu_counters(proc_root, errors)
    time.sleep(sample_interval)
    usage = cpu_usage(before, cpu_counters(proc_root, errors), errors)
    temperature, fans = sensors(sys_root, errors)
    clock = frequency(sys_root, errors)

    pstate = sys_root / "devices/system/cpu/intel_pstate"
    no_turbo = read_int(pstate / "no_turbo", errors) if (pstate / "no_turbo").exists() else None
    limit = read_int(pstate / "max_perf_pct", errors) if (pstate / "max_perf_pct").exists() else None
    if no_turbo is not None and no_turbo not in (0, 1):
        errors.append("Intel P-state: invalid Turbo Boost state")
        no_turbo = None
    if limit is not None and not 0 <= limit <= 100:
        errors.append("Intel P-state: invalid performance limit")
        limit = None

    return {
        "temperature_c": temperature,
        "fans": fans,
        "usage_percent": usage,
        "frequency_mhz": clock,
        "turbo_enabled": no_turbo == 0 if no_turbo is not None else None,
        "performance_limit_percent": limit,
        "errors": list(dict.fromkeys(errors)),
    }


if __name__ == "__main__":
    print(json.dumps(collect_metrics(), allow_nan=False))
