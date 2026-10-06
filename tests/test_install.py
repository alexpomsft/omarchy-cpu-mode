import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = self.root / "config"
        self.plugin = self.config / "omarchy/plugins/local.cpu-mode"
        self.log = self.root / "commands.log"
        commands = self.root / "commands"
        commands.mkdir()
        for name, content in {
            "omarchy": 'printf "omarchy %s\\n" "$*" >> "$TEST_LOG"\n',
            "pkexec": 'printf "pkexec %s\\n" "$*" >> "$TEST_LOG"\ncat >/dev/null\n',
        }.items():
            path = commands / name
            path.write_text("#!/bin/sh\n" + content)
            path.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": str(commands) + os.pathsep + os.environ["PATH"],
            "XDG_CONFIG_HOME": str(self.config),
            "TEST_LOG": str(self.log),
            "USER": "test-user",
        }

    def checkout(self, path):
        path.mkdir(parents=True)
        for filename in (
            "install.sh", "manifest.json", "cpu-metrics.py", "BarWidget.qml",
            "bin/omarchy-cpu-mode", "polkit/49-omarchy-cpu-mode.rules.in",
        ):
            target = path / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPOSITORY / filename, target)
        return path

    def install(self, checkout):
        result = subprocess.run(
            ["bash", str(checkout / "install.sh")],
            env=self.environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CPU Mode installed.", result.stdout)
        commands = self.log.read_text()
        self.assertIn("pkexec install -o root -g root -m 0755", commands)
        self.assertIn(f"omarchy plugin validate {self.plugin}", commands)
        self.assertIn("omarchy plugin enable local.cpu-mode --section right", commands)

    def test_install_from_separate_checkout_copies_widget_files(self):
        checkout = self.checkout(self.root / "checkout")
        self.install(checkout)
        for filename in ("manifest.json", "cpu-metrics.py", "BarWidget.qml"):
            target = self.plugin / filename
            self.assertEqual(target.read_bytes(), (checkout / filename).read_bytes())
            self.assertEqual(target.stat().st_mode & 0o777, 0o644)

    def test_install_from_marketplace_checkout_does_not_copy_onto_itself(self):
        checkout = self.checkout(self.plugin)
        originals = {
            filename: (checkout / filename).read_bytes()
            for filename in ("manifest.json", "cpu-metrics.py", "BarWidget.qml")
        }
        self.install(checkout)
        for filename, content in originals.items():
            self.assertEqual((checkout / filename).read_bytes(), content)

    def test_install_handles_symlinked_config_directory(self):
        actual_config = self.root / "actual-config"
        checkout = self.checkout(actual_config / "omarchy/plugins/local.cpu-mode")
        self.config.symlink_to(actual_config, target_is_directory=True)
        self.install(checkout)


if __name__ == "__main__":
    unittest.main()
