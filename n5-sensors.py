#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read Minisforum N5 hwmon temperatures and fan speeds."""

import argparse
import errno
import json
import sys
from pathlib import Path

HWMON_ROOT = Path("/sys/class/hwmon")
DRIVER_NAME = "minisforum_n5_it5571"
TEMPERATURES = ("cpu", "system", "board", "ambient")
FANS = ("cpu", "ssd", "hdd")


def find_device(root):
    matches = []
    for path in sorted(root.glob("hwmon*")):
        try:
            name = (path / "name").read_text().strip()
        except FileNotFoundError:
            continue
        if name == DRIVER_NAME:
            matches.append(path)
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


def read_sensors(root):
    device = find_device(root)
    temperatures = {
        name: read_value(device / f"temp{index}_input", temperature=True)
        for index, name in enumerate(TEMPERATURES, 1)
    }
    fans = {
        name: read_value(device / f"fan{index}_input")
        for index, name in enumerate(FANS, 1)
    }
    # The driver exports fan4 as zero without a tachometer, not a measured RPM.
    fans["pcie"] = None
    return {"temperatures_c": temperatures, "fans_rpm": fans}


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
        print("Fans (RPM):")
        for name, value in sensors["fans_rpm"].items():
            print(f"  {name}: {value}" if value is not None else f"  {name}: unavailable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
