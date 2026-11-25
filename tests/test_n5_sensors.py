#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import contextlib
import errno
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "n5-sensors.py"
spec = importlib.util.spec_from_file_location("n5_sensors", SCRIPT)
sensors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sensors)


class SensorsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.device = self.root / "hwmon7"
        self.device.mkdir()
        (self.device / "name").write_text("minisforum_n5_it5571\n")
        for index, value in enumerate((42500, 33000, 28500, 21000), 1):
            (self.device / f"temp{index}_input").write_text(f"{value}\n")
        for index, value in enumerate((1200, 0, 850), 1):
            (self.device / f"fan{index}_input").write_text(f"{value}\n")

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sensors, "HWMON_ROOT", self.root), \
             mock.patch("sys.argv", ["n5-sensors.py", *args]), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = sensors.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_json_is_script_friendly_and_does_not_report_fake_pcie_rpm(self):
        (self.root / "hwmon0").mkdir()
        (self.root / "hwmon0" / "name").write_text("other\n")
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), {
            "temperatures_c": {"cpu": 42.5, "system": 33.0, "board": 28.5, "ambient": 21.0},
            "fans_rpm": {"cpu": 1200, "ssd": 0, "hdd": 850, "pcie": None},
        })

    def test_missing_device_and_read_errors_fail_without_partial_output(self):
        (self.device / "name").write_text("other\n")
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stdout), (1, ""))
        self.assertIn("device not found", stderr)
        (self.device / "name").write_text("minisforum_n5_it5571\n")
        (self.device / "fan2_input").unlink()
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stdout), (1, ""))
        self.assertIn("fan2_input", stderr)

    def test_unavailable_temperature_is_null_with_warning(self):
        original = Path.read_text

        def read_text(path, *args, **kwargs):
            if path == self.device / "temp2_input":
                raise OSError(errno.ENODATA, "No data available")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", read_text):
            status, stdout, stderr = self.run_cli("--json")
        self.assertEqual(status, 0)
        self.assertIsNone(json.loads(stdout)["temperatures_c"]["system"])
        self.assertIn("temp2_input", stderr)

    def test_invalid_fan_and_duplicate_device_fail(self):
        (self.device / "fan1_input").write_text("-1\n")
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stdout), (1, ""))
        self.assertIn("negative fan speed", stderr)
        other = self.root / "hwmon8"
        other.mkdir()
        (other / "name").write_text("minisforum_n5_it5571\n")
        status, stdout, stderr = self.run_cli()
        self.assertEqual((status, stdout), (1, ""))
        self.assertIn("multiple N5", stderr)


if __name__ == "__main__":
    unittest.main()
