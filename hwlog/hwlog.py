#!/usr/bin/env python3
"""Log hardware sensors of this host to InfluxDB.

Without --write the line protocol is only printed (dry run).
Connection settings live in a config file (default: /etc/hwlog.conf).

Modes:
  fast   sensors, memory/swap, load, SATA disk temperatures (every ~30s)
  smart  SMART attributes and overall health of all drives  (every ~15min)
  all    everything (default, handy for dry runs)
"""
import argparse
import base64
import configparser
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_CONFIG = "/etc/hwlog.conf"
# (field name in InfluxDB, key in /proc/meminfo) -> logged in bytes
MEM_FIELDS = [
    ("total",      "MemTotal"),
    ("free",       "MemFree"),
    ("available",  "MemAvailable"),
    ("swap_total", "SwapTotal"),
    ("swap_free",  "SwapFree"),
]

def warn(msg):
    print(f"hwlog: {msg}", file=sys.stderr)


def run_json(cmd):
    """Run a command and parse its stdout as JSON (exit code is ignored,
    smartctl uses it as a bitmask). Returns None on failure."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        warn(f"{cmd[0]} failed: {e}")
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def get_value(data, chip, label, kind):
    """Find e.g. temp1_input for a chip/label; prefer *_input over *_average."""
    entry = data.get(chip, {}).get(label)
    if not isinstance(entry, dict):
        return None
    pattern = re.compile(rf"^{kind}\d*_(input|average)$")
    candidates = [(k, v) for k, v in entry.items()
                  if pattern.match(k) and isinstance(v, (int, float))]
    candidates.sort(key=lambda kv: kv[0].endswith("_average"))
    return candidates[0][1] if candidates else None


def esc(s):
    """Escape a tag value for line protocol."""
    return re.sub(r"([ ,=])", r"\\\1", str(s))


def fval(v):
    """Format a field value: strings are quoted, everything else is a float."""
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return repr(float(v))


def line(measurement, host, tags, fields, ts):
    tag_str = "".join(f",{k}={esc(v)}" for k, v in tags.items())
    field_str = ",".join(f"{k}={fval(v)}" for k, v in fields.items())
    return f"{measurement},host={esc(host)}{tag_str} {field_str} {ts}"


def sensor_lines(host, ts, sensors):
    data = run_json(["sensors", "-j"])
    if data is None:
        warn("could not read 'sensors -j'")
        return []
    lines = []
    for measurement, tag_key, tag_val, chip, label, kind in sensors:
        value = get_value(data, chip, label, kind)
        if value is None:
            warn(f"no value for {chip} / {label}")
            continue
        lines.append(line(measurement, host, {tag_key: tag_val}, {"value": value}, ts))
    return lines


def system_lines(host, ts):
    """Memory/swap (bytes) and load averages."""
    lines = []

    mem = {}
    try:
        with open("/proc/meminfo") as f:
            for entry in f:
                key, _, rest = entry.partition(":")
                parts = rest.split()
                if parts:
                    mem[key] = int(parts[0]) * 1024   # /proc/meminfo reports KiB
    except OSError as e:
        warn(f"cannot read /proc/meminfo: {e}")
    fields = {name: mem[key] for name, key in MEM_FIELDS if key in mem}
    if fields:
        lines.append(line("memory", host, {}, fields, ts))

    try:
        l1, l5, l15 = os.getloadavg()
        lines.append(line("load", host, {}, {"load1": l1, "load5": l5, "load15": l15}, ts))
    except OSError as e:
        warn(f"cannot read load average: {e}")

    return lines


def drive_devices():
    """Yield SATA (sdX) and NVMe (nvmeXnY) disks."""
    try:
        out = subprocess.run(["lsblk", "-dno", "NAME,TYPE"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        warn(f"lsblk failed: {e}")
        return
    for entry in out.splitlines():
        parts = entry.split()
        if (len(parts) == 2 and parts[1] == "disk"
                and parts[0].startswith(("sd", "nvme"))):
            yield parts[0]


def is_rotating(info, dev):
    rate = info.get("rotation_rate")
    if rate is not None:
        return rate > 0
    try:  # fall back to the kernel's idea of it
        with open(f"/sys/block/{dev}/queue/rotational") as f:
            return f.read().strip() == "1"
    except OSError:
        return False


def raw_int(attr):
    """Raw value as an integer. Uses the leading number of smartctl's raw
    string, which handles formats like '12345h+23m+10.5s'."""
    raw = attr.get("raw", {})
    m = re.match(r"\d+", str(raw.get("string", "")).strip())
    if m:
        return int(m.group())
    return raw.get("value")


def drive_lines(host, ts, want_temp, want_smart, hdd_attrs, ssd_attrs, nvme_fields):
    lines = []
    for dev in drive_devices():
        is_nvme = dev.startswith("nvme")
        if is_nvme and not want_smart:
            continue  # NVMe temperatures come from lm-sensors, nothing to do here

        cmd = ["smartctl", "-j", "-i", "-A"]
        if want_smart:
            cmd.append("-H")
        if not is_nvme:
            cmd += ["-n", "standby"]   # never wake a sleeping HDD
        info = run_json(cmd + [f"/dev/{dev}"])
        if not info:
            continue

        nvme_log = info.get("nvme_smart_health_information_log")
        ata_table = info.get("ata_smart_attributes", {}).get("table")
        if nvme_log is None and ata_table is None:
            continue  # drive in standby or no SMART data

        serial = re.sub(r"[ ,=]", "_", info.get("serial_number", "unknown"))
        model = re.sub(r"[ ,=]", "_", info.get("model_name", "unknown"))
        base = {"serial": serial, "model": model, "dev": dev}

        if nvme_log is not None:
            dtype = "nvme"
            metrics = {name: nvme_log.get(key) for key, name in nvme_fields}
        else:
            dtype = "hdd" if is_rotating(info, dev) else "ssd"
            attrs = {a["name"]: a for a in ata_table if "name" in a}
            metrics = {}
            for attr_name, metric, source in (hdd_attrs if dtype == "hdd" else ssd_attrs):
                a = attrs.get(attr_name)
                if a is None:
                    continue
                metrics[metric] = raw_int(a) if source == "raw" else a.get("value")
            temp = info.get("temperature", {}).get("current")
            if want_temp and temp is not None:
                lines.append(line("disk_temp", host, base, {"value": temp}, ts))

        if not want_smart:
            continue

        tags = {**base, "type": dtype}
        for metric, value in metrics.items():
            if value is not None:
                lines.append(line("disk_smart", host,
                                  {**tags, "attribute": metric},
                                  {"value": value}, ts))

        passed = info.get("smart_status", {}).get("passed")
        if passed is not None:
            lines.append(line("disk_health", host, tags,
                              {"status": "PASSED" if passed else "FAILED",
                               "passed": 1 if passed else 0}, ts))
    return lines


def collect(host, mode, config):
    ts = int(time.time())
    fast = mode in ("fast", "all")
    smart = mode in ("smart", "all")

    lines = []
    if fast:
        lines += sensor_lines(host, ts, config["sensors"])
        lines += system_lines(host, ts)
    lines += drive_lines(host, ts, want_temp=fast, want_smart=smart,
                         hdd_attrs=config["hdd_attrs"],
                         ssd_attrs=config["ssd_attrs"],
                         nvme_fields=config["nvme_fields"])
    return lines


def load_config(path):
    cfg = configparser.ConfigParser()
    if not cfg.read(path):
        warn(f"cannot read config file {path}")
        sys.exit(1)

    required = ("influxdb", "sensors", "hdd_attrs", "ssd_attrs", "nvme_fields")
    missing = [section for section in required if section not in cfg]
    if missing:
        warn(f"{path}: missing sections: {', '.join('[' + s + ']' for s in missing)}")
        sys.exit(1)

    result = {"influxdb": cfg["influxdb"]}
    shapes = {
        "sensors": 6,
        "hdd_attrs": 3,
        "ssd_attrs": 3,
        "nvme_fields": 2,
    }
    for section, width in shapes.items():
        if "items" not in cfg[section]:
            warn(f"{path}: [{section}] missing items")
            sys.exit(1)
        try:
            items = json.loads(cfg[section]["items"])
        except json.JSONDecodeError as e:
            warn(f"{path}: [{section}] items must be valid JSON: {e}")
            sys.exit(1)
        if not isinstance(items, list) or any(
                not isinstance(item, list) or len(item) != width
                for item in items):
            warn(f"{path}: [{section}] items must be an array of {width}-item arrays")
            sys.exit(1)
        result[section] = [tuple(item) for item in items]
    return result


def write(lines, s):
    url = s.get("url", "").rstrip("/")
    token = s.get("token", "").strip()
    headers = {}

    if token:  # InfluxDB 2.x / 3.x
        qs = urllib.parse.urlencode({"org": s.get("org", ""),
                                     "bucket": s.get("bucket", ""),
                                     "precision": "s"})
        endpoint = f"{url}/api/v2/write?{qs}"
        headers["Authorization"] = f"Token {token}"
    else:      # InfluxDB 1.x
        qs = urllib.parse.urlencode({"db": s.get("database", ""), "precision": "s"})
        endpoint = f"{url}/write?{qs}"
        if s.get("username"):
            cred = f"{s['username']}:{s.get('password', '')}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(cred).decode()

    req = urllib.request.Request(endpoint, data=("\n".join(lines) + "\n").encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError as e:
        warn(f"InfluxDB returned HTTP {e.code}: {e.read().decode(errors='replace')}")
        sys.exit(1)
    except (urllib.error.URLError, OSError) as e:
        warn(f"could not reach InfluxDB: {e}")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="send the data to InfluxDB (default: only print it)")
    ap.add_argument("--mode", choices=("fast", "smart", "all"), default="all",
                    help="what to collect (default: all)")
    ap.add_argument("--config", default=DEFAULT_CONFIG,
                    help=f"config file (default: {DEFAULT_CONFIG})")
    args = ap.parse_args()

    config = load_config(args.config)
    lines = collect(socket.gethostname(), args.mode, config)

    if not args.write:
        print("\n".join(lines))
        return
    if not lines:
        warn("nothing to write")
        sys.exit(1)
    write(lines, config["influxdb"])


if __name__ == "__main__":
    main()