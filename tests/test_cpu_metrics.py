import errno
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "cpu_metrics", Path(__file__).resolve().parents[1] / "cpu-metrics.py"
)
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


class CpuMetricsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.sys = self.root / "sys"
        self.proc = self.root / "proc"

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(value))
        return target

    def sensor(self, device, name, values):
        self.write(f"sys/class/hwmon/{device}/name", name)
        for key, value in values.items():
            self.write(f"sys/class/hwmon/{device}/{key}", value)

    def test_cpu_package_temperature_ignores_other_devices_and_hotter_cores(self):
        self.sensor("hwmon0", "nvme", {"temp1_input": 99000})
        self.sensor("hwmon1", "coretemp", {
            "temp1_input": 52000, "temp1_label": "Package id 0",
            "temp2_input": 55000, "temp2_label": "Core 0",
        })
        self.sensor("hwmon2", "coretemp", {
            "temp1_input": 54000, "temp1_label": "Package id 1",
        })
        errors = []
        temperature, fans = metrics.sensors(self.sys, errors)
        self.assertEqual(temperature, 54)
        self.assertEqual(fans, [])
        self.assertEqual(errors, [])

    def test_cpu_core_and_thermal_zone_fallbacks(self):
        self.sensor("hwmon0", "coretemp", {"temp1_input": 44000})
        self.assertEqual(metrics.sensors(self.sys, [])[0], 44)
        self.write("sys/class/hwmon/hwmon0/name", "nvme")
        self.write("sys/class/thermal/thermal_zone0/type", "acpitz")
        self.write("sys/class/thermal/thermal_zone0/temp", 88000)
        self.write("sys/class/thermal/thermal_zone1/type", "x86_pkg_temp")
        self.write("sys/class/thermal/thermal_zone1/temp", 47000)
        self.assertEqual(metrics.sensors(self.sys, [])[0], 47)

    def test_amd_die_temperature_preferred_to_control_temperature(self):
        self.sensor("hwmon0", "k10temp", {
            "temp1_input": 70000, "temp1_label": "Tctl",
            "temp2_input": 50000, "temp2_label": "Tdie",
        })
        self.assertEqual(metrics.sensors(self.sys, [])[0], 50)

    def test_fans_keep_zero_rpm_and_labels(self):
        self.sensor("hwmon0", "thinkpad", {
            "fan1_input": 0, "fan1_label": "CPU fan", "fan2_input": 2100,
        })
        temperature, fans = metrics.sensors(self.sys, [])
        self.assertIsNone(temperature)
        self.assertEqual(fans, [
            {"label": "thinkpad: CPU fan", "rpm": 0},
            {"label": "thinkpad: fan2", "rpm": 2100},
        ])

    def test_legacy_hwmon_reads_fans_from_device_symlink(self):
        legacy = self.write("sys/devices/platform/applesmc/name", "applesmc").parent
        self.write("sys/devices/platform/applesmc/fan1_input", 2200)
        self.write("sys/devices/platform/applesmc/fan2_input", 0)
        device = self.sys / "class/hwmon/hwmon0"
        device.mkdir(parents=True)
        (device / "device").symlink_to(legacy, target_is_directory=True)
        self.sensor("hwmon1", "coretemp", {"temp1_input": 49000})
        errors = []
        temperature, fans = metrics.sensors(self.sys, errors)
        self.assertEqual(temperature, 49)
        self.assertEqual(fans, [
            {"label": "applesmc: fan1", "rpm": 2200},
            {"label": "applesmc: fan2", "rpm": 0},
        ])
        self.assertEqual(errors, [])

    def test_modern_hwmon_does_not_duplicate_parent_device_sensors(self):
        self.sensor("hwmon0", "applesmc", {"fan1_input": 2200})
        self.write("sys/class/hwmon/hwmon0/device/name", "applesmc")
        self.write("sys/class/hwmon/hwmon0/device/fan1_input", 2200)
        errors = []
        _, fans = metrics.sensors(self.sys, errors)
        self.assertEqual(fans, [{"label": "applesmc: fan1", "rpm": 2200}])
        self.assertEqual(errors, [])

    def test_unsupported_optional_fan_label_uses_sensor_name(self):
        self.sensor("hwmon0", "applesmc", {"fan1_input": 2200, "fan1_label": ""})
        errors = []
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path.name == "fan1_label":
                raise OSError(errno.EINVAL, "Invalid argument")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            _, fans = metrics.sensors(self.sys, errors)
        self.assertEqual(fans, [{"label": "applesmc: fan1", "rpm": 2200}])
        self.assertEqual(errors, [])

    def test_fan_label_permission_failure_is_still_reported(self):
        self.sensor("hwmon0", "applesmc", {"fan1_input": 2200, "fan1_label": ""})
        errors = []
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path.name == "fan1_label":
                raise PermissionError(errno.EACCES, "Permission denied")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            _, fans = metrics.sensors(self.sys, errors)
        self.assertEqual(fans, [{"label": "applesmc: fan1", "rpm": 2200}])
        self.assertEqual(len(errors), 1)
        self.assertIn("Permission denied", errors[0])

    def test_missing_sensors_are_not_zero_readings(self):
        self.assertEqual(metrics.sensors(self.sys, []), (None, []))
        self.assertIsNone(metrics.frequency(self.sys, []))

    def test_invalid_sensor_does_not_discard_valid_sensor(self):
        self.sensor("hwmon0", "coretemp", {
            "temp1_input": "bad", "temp2_input": 51000, "fan1_input": -1,
        })
        errors = []
        temperature, fans = metrics.sensors(self.sys, errors)
        self.assertEqual(temperature, 51)
        self.assertEqual(fans, [{"label": "coretemp: fan1", "rpm": None}])
        self.assertEqual(len(errors), 2)
        self.assertIn("invalid integer", errors[0])
        self.assertIn("negative fan speed", errors[1])

    def test_unreadable_sensor_is_reported(self):
        self.sensor("hwmon0", "coretemp", {"temp1_input": 50000})
        errors = []
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path.name == "temp1_input":
                raise PermissionError("permission denied")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            self.assertEqual(metrics.sensors(self.sys, errors), (None, []))
        self.assertIn("permission denied", errors[0])

    def test_unreadable_fan_is_unavailable_not_unsupported(self):
        self.sensor("hwmon0", "thinkpad", {"fan1_input": 2000})
        errors = []
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path.name == "fan1_input":
                raise OSError("device busy")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            _, fans = metrics.sensors(self.sys, errors)
        self.assertEqual(fans, [{"label": "thinkpad: fan1", "rpm": None}])
        self.assertIn("device busy", errors[0])

    def test_frequency_averages_cpufreq_policies(self):
        self.write("sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq", 1200000)
        self.write("sys/devices/system/cpu/cpufreq/policy1/scaling_cur_freq", 1800000)
        self.assertEqual(metrics.frequency(self.sys, []), 1500)

    def test_cpu_usage_excludes_guest_and_counts_iowait_as_idle(self):
        self.write("proc/stat", "cpu 100 10 20 800 50 5 5 10 100 10\ncpu0 1 2 3 4\n")
        errors = []
        before = metrics.cpu_counters(self.proc, errors)
        self.assertEqual(before, (1000, 850))
        self.write("proc/stat", "cpu 120 10 25 850 75 5 5 10 110 10\n")
        after = metrics.cpu_counters(self.proc, errors)
        self.assertEqual(metrics.cpu_usage(before, after, errors), 25)
        self.assertEqual(errors, [])

    def test_cpu_usage_reports_invalid_and_reset_counters(self):
        self.write("proc/stat", "not cpu counters")
        errors = []
        self.assertIsNone(metrics.cpu_counters(self.proc, errors))
        self.assertIsNone(metrics.cpu_usage((100, 50), (90, 40), errors))
        self.assertIsNone(metrics.cpu_usage((100, 50), (100, 50), errors))
        self.assertEqual(len(errors), 3)

    def test_collect_metrics_json_shape_and_quiet_policy(self):
        self.write("proc/stat", "cpu 1 0 0 99 0 0 0 0\n")
        self.write("sys/devices/system/cpu/intel_pstate/no_turbo", 1)
        self.write("sys/devices/system/cpu/intel_pstate/max_perf_pct", 60)
        with patch.object(metrics, "cpu_counters", side_effect=[(100, 90), (200, 170)]):
            result = metrics.collect_metrics(self.sys, self.proc, sample_interval=0)
        self.assertEqual(result, {
            "temperature_c": None, "fans": [], "usage_percent": 20,
            "frequency_mhz": None, "turbo_enabled": False,
            "performance_limit_percent": 60, "errors": [],
        })
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)

    def test_collect_metrics_reads_full_policy_without_changing_it(self):
        turbo_path = self.write("sys/devices/system/cpu/intel_pstate/no_turbo", 0)
        limit_path = self.write("sys/devices/system/cpu/intel_pstate/max_perf_pct", 100)
        with patch.object(metrics, "cpu_counters", side_effect=[(100, 90), (200, 170)]):
            result = metrics.collect_metrics(self.sys, self.proc, sample_interval=0)
        self.assertTrue(result["turbo_enabled"])
        self.assertEqual(result["performance_limit_percent"], 100)
        self.assertEqual(turbo_path.read_text(), "0")
        self.assertEqual(limit_path.read_text(), "100")

    def test_invalid_pstate_values_are_unavailable_with_errors(self):
        self.write("sys/devices/system/cpu/intel_pstate/no_turbo", 2)
        self.write("sys/devices/system/cpu/intel_pstate/max_perf_pct", 101)
        with patch.object(metrics, "cpu_counters", side_effect=[(100, 90), (200, 170)]):
            result = metrics.collect_metrics(self.sys, self.proc, sample_interval=0)
        self.assertIsNone(result["turbo_enabled"])
        self.assertIsNone(result["performance_limit_percent"])
        self.assertEqual(len(result["errors"]), 2)


if __name__ == "__main__":
    unittest.main()
