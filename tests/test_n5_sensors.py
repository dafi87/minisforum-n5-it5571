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
        self.dmi = self.root / "dmi"
        self.dmi.mkdir()
        (self.dmi / "product_name").write_text("N5\n")
        (self.dmi / "board_name").write_text("F8NAA\n")
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
             mock.patch.object(sensors, "DMI_ROOT", self.dmi), \
             mock.patch("sys.argv", ["n5-sensors.py", *args]), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = sensors.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def add_extra_sensor(self, hwmon, name, value, device=None):
        path = self.root / hwmon
        path.mkdir()
        (path / "name").write_text(f"{name}\n")
        (path / "temp1_input").write_text(f"{value}\n")
        if device is not None:
            target = self.root / "devices" / device
            target.mkdir(parents=True, exist_ok=True)
            (path / "device").symlink_to(target)
        return path

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

    def test_air_omits_unverified_temperatures_with_old_or_new_driver(self):
        (self.dmi / "board_name").write_text("F8NAB\n")
        for product in ("N5A", "N5 AIR"):
            (self.dmi / "product_name").write_text(f"{product}\n")
            status, stdout, stderr = self.run_cli("--json")
            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout)["temperatures_c"],
                             {"cpu": 42.5, "system": 33.0})
        (self.device / "temp3_input").unlink()
        (self.device / "temp4_input").unlink()
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["temperatures_c"],
                         {"cpu": 42.5, "system": 33.0})

    def test_dmi_failure_and_other_board_missing_sensors_are_errors(self):
        (self.dmi / "product_name").unlink()
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stdout), (1, ""))
        self.assertIn("product_name", stderr)
        (self.dmi / "product_name").write_text("N5A\n")
        (self.device / "temp3_input").unlink()
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stdout), (1, ""))
        self.assertIn("temp3_input", stderr)

    def test_memory_and_nics_are_discovered_without_hwmon_number_dependence(self):
        self.add_extra_sensor("hwmon4", "spd5118", 22750, "0-0051")
        self.add_extra_sensor("hwmon5", "spd5118", 23500, "0-0052")
        self.add_extra_sensor("hwmon1", "r8169_0_300:00", 27500)
        self.add_extra_sensor("hwmon2", "r8169_0_200:00", 26000)
        self.add_extra_sensor("hwmon3", "k10temp", 25000)

        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stderr), (0, ""))
        result = json.loads(stdout)
        self.assertEqual(result["memory_temperatures_c"],
                         {"0-0051": 22.75, "0-0052": 23.5})
        self.assertEqual(result["nic_temperatures_c"],
                         {"r8169_0_200:00": 26.0, "r8169_0_300:00": 27.5})

        (self.root / "hwmon1").rename(self.root / "hwmon9")
        (self.root / "hwmon4").rename(self.root / "hwmon10")
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stderr), (0, ""))
        self.assertEqual(json.loads(stdout), result)
        status, stdout, stderr = self.run_cli()
        self.assertEqual((status, stderr), (0, ""))
        self.assertIn("0-0051: 22.750", stdout)
        self.assertIn("r8169_0_200:00: 26.000", stdout)

    def test_optional_groups_are_only_included_when_present(self):
        self.add_extra_sensor("hwmon0", "r8169_0_200:00", 26000)
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stderr), (0, ""))
        result = json.loads(stdout)
        self.assertNotIn("memory_temperatures_c", result)
        self.assertEqual(result["nic_temperatures_c"], {"r8169_0_200:00": 26.0})

    def test_extra_sensor_read_failure_and_duplicate_identity_are_errors(self):
        path = self.add_extra_sensor("hwmon0", "spd5118", 22750, "0-0051")
        (path / "temp1_input").unlink()
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stdout), (1, ""))
        self.assertIn("temp1_input", stderr)
        (path / "temp1_input").write_text("22750\n")
        self.add_extra_sensor("hwmon1", "spd5118", 23000, "0-0051")
        status, stdout, stderr = self.run_cli("--json")
        self.assertEqual((status, stdout), (1, ""))
        self.assertIn("duplicate sensor identity", stderr)


if __name__ == "__main__":
    unittest.main()
