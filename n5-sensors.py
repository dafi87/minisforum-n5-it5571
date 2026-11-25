#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read Minisforum N5 hwmon temperatures and fan speeds."""

import argparse
import errno
import json
import sys
from pathlib import Path

HWMON_ROOT = Path("/sys/class/hwmon")
DMI_ROOT = Path("/sys/class/dmi/id")
DRIVER_NAME = "minisforum_n5_it5571"
TEMPERATURES = ("cpu", "system", "board", "ambient")
FANS = ("cpu", "ssd", "hdd")


def find_devices(root):
    devices = []
    for path in sorted(root.glob("hwmon*")):
        try:
            name = (path / "name").read_text().strip()
        except FileNotFoundError:
            continue
        devices.append((path, name))
    return devices


def find_n5_device(devices):
    matches = [path for path, name in devices if name == DRIVER_NAME]
    if not matches:
        raise RuntimeError(
            "N5 hwmon device not found; check that the driver loaded and bound "
            "(see dmesg)"
        )
    if len(matches) != 1:
        raise RuntimeError("multiple N5 hwmon devices found; cannot select one")
    return matches[0]


def read_value(path, *, temperature=False):
    try:
        text = path.read_text().strip()
    except OSError as exc:
        if temperature and exc.errno == errno.ENODATA:
            print(f"warning: {path} has no temperature data", file=sys.stderr)
            return None
        raise RuntimeError(f"cannot read {path}: {exc.strerror}") from exc
    try:
        value = int(text)
    except ValueError as exc:
        raise RuntimeError(f"invalid numeric value in {path}: {text!r}") from exc
    if not temperature and value < 0:
        raise RuntimeError(f"invalid negative fan speed in {path}: {value}")
    return value / 1000 if temperature else value


def read_extra_temperatures(devices):
    memory = {}
    nics = {}
    for path, name in devices:
        if name == "spd5118":
            group = memory
            identity = (path / "device").resolve(strict=True).name
        elif name.startswith("r8169_"):
            group = nics
            identity = name
        else:
            continue
        if identity in group:
            raise RuntimeError(f"duplicate sensor identity {identity!r}")
        group[identity] = read_value(path / "temp1_input", temperature=True)
    extra = {}
    if memory:
        extra["memory_temperatures_c"] = memory
    if nics:
        extra["nic_temperatures_c"] = nics
    return extra


def read_sensors(root):
    devices = find_devices(root)
    device = find_n5_device(devices)
    product = (DMI_ROOT / "product_name").read_text().strip()
    board = (DMI_ROOT / "board_name").read_text().strip()
    temperature_names = TEMPERATURES[:2] if (
        product in ("N5A", "N5 AIR") and board == "F8NAB"
    ) else TEMPERATURES
    temperatures = {
        name: read_value(device / f"temp{index}_input", temperature=True)
        for index, name in enumerate(temperature_names, 1)
    }
    fans = {
        name: read_value(device / f"fan{index}_input")
        for index, name in enumerate(FANS, 1)
    }
    # The driver exports fan4 as zero without a tachometer, not a measured RPM.
    fans["pcie"] = None
    result = {"temperatures_c": temperatures, "fans_rpm": fans}
    result.update(read_extra_temperatures(devices))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="output JSON for scripts")
    args = parser.parse_args()
    try:
        sensors = read_sensors(HWMON_ROOT)
    except (OSError, RuntimeError) as exc:
        print(f"n5-sensors: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(sensors))
    else:
        print("Temperatures (C):")
        for name, value in sensors["temperatures_c"].items():
            print(f"  {name}: {value:.3f}" if value is not None else f"  {name}: unavailable")
        for key, label in (("memory_temperatures_c", "Memory"),
                           ("nic_temperatures_c", "NIC")):
            if key in sensors:
                print(f"{label} temperatures (C):")
                for name, value in sensors[key].items():
                    print(f"  {name}: {value:.3f}" if value is not None
                          else f"  {name}: unavailable")
        print("Fans (RPM):")
        for name, value in sensors["fans_rpm"].items():
            print(f"  {name}: {value}" if value is not None else f"  {name}: unavailable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
