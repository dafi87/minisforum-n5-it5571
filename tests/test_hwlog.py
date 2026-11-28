#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "hwlog" / "hwlog.py"
spec = importlib.util.spec_from_file_location("hwlog", SCRIPT)
hwlog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hwlog)


class HwlogConfigTest(unittest.TestCase):
    def test_load_config_reads_all_collection_mappings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hwlog.conf"
            path.write_text("""
[influxdb]
url = http://127.0.0.1:8086

[sensors]
items = [["temperature", "sensor", "custom", "custom-chip", "temp1", "temp"]]

[hdd_attrs]
items = [["Power_On_Hours", "hours", "raw"]]

[ssd_attrs]
items = [["Remaining_Lifetime_Perc", "life", "raw"]]

[nvme_fields]
items = [["percentage_used", "used"]]
""")

            config = hwlog.load_config(path)

        self.assertEqual(config["sensors"], [
            ("temperature", "sensor", "custom", "custom-chip", "temp1", "temp"),
        ])
        self.assertEqual(config["hdd_attrs"], [
            ("Power_On_Hours", "hours", "raw"),
        ])
        self.assertEqual(config["ssd_attrs"], [
            ("Remaining_Lifetime_Perc", "life", "raw"),
        ])
        self.assertEqual(config["nvme_fields"], [
            ("percentage_used", "used"),
        ])


if __name__ == "__main__":
    unittest.main()
