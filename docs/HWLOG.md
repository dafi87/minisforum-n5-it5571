# Host health logging to InfluxDB

The optional `hwlog` script collects host sensors, memory, load and disk health
and writes InfluxDB line protocol. It runs separately from `n5-sensors.py` and
does not add anything to the Proxmox web UI.

## Prerequisites

Run the commands below as root on the Proxmox host. Install and validate the
N5 driver as described in the [Proxmox setup guide](PROXMOX.md) if you want its
temperature and fan readings. Other available sensors and system metrics can
still be collected without it.

Install the tools used by the script:

```bash
apt update
apt install python3 lm-sensors smartmontools util-linux
```

The script uses Python's standard library; no Python packages are needed.
Verify that `sensors -j`, `lsblk -dno NAME,TYPE`, and `smartctl` work on the
host. SMART access generally requires root; the supplied services run as root.

The supplied service files expect the checkout at
`/usr/local/src/minisforum-n5-it5571`. If you followed the Proxmox setup guide,
reuse that checkout; otherwise clone it there:

```bash
cd /usr/local/src
git clone https://github.com/dafi87/minisforum-n5-it5571.git
```

If you use another checkout location, edit `ExecStart` in **both** service
files before installing them. Ensure the script is executable:

```bash
chmod 755 /usr/local/src/minisforum-n5-it5571/hwlog/hwlog.py
```

Use your actual checkout path for this and subsequent commands if it differs.
The checkout must remain in place because the services execute the script there.

## Configure InfluxDB

Create the destination database or bucket on your InfluxDB server and ensure
the host can reach it. Copy the example configuration, unless you already have
an `/etc/hwlog.conf` you want to keep:

```bash
install -m 600 /usr/local/src/minisforum-n5-it5571/hwlog/hwlog.conf /etc/hwlog.conf
editor /etc/hwlog.conf
```

Set `url` to the server URL. The script selects the API based on `token`:

- **InfluxDB 2.x**, or **3.x with the compatible v2 write endpoint**: set
  `token`, `org`, and `bucket`. The token needs write access to the bucket.
- **InfluxDB 1.x**: leave `token` empty and set `database`; set `username` and
  `password` if authentication is enabled.

The script sends to `/api/v2/write` for a nonempty token and `/write` otherwise.
Use HTTPS when transmitting credentials over an untrusted network. Keep the
configuration root-readable only and do not share its credentials.

## Test and enable

First inspect the line protocol without sending anything:

```bash
/usr/local/src/minisforum-n5-it5571/hwlog/hwlog.py --mode all
```

The default is a dry run, and does not read the configuration. Warnings about
missing sensors can be expected when the host does not have the hard-coded
devices. Compare their chip names and labels with `sensors -j`; adjust the
`SENSORS` mapping in `hwlog.py` if your host enumerates them differently.
Missing readings are skipped.

Test a write using `/etc/hwlog.conf`:

```bash
/usr/local/src/minisforum-n5-it5571/hwlog/hwlog.py --mode all --write
```

Check the destination database or bucket for points tagged with the host's
hostname. To use another configuration file for a manual run, add
`--config /path/to/hwlog.conf`.

Install the service and timer units and enable both timers:

```bash
install -m 644 /usr/local/src/minisforum-n5-it5571/hwlog/hwlog.service /usr/local/src/minisforum-n5-it5571/hwlog/hwlog.timer /usr/local/src/minisforum-n5-it5571/hwlog/hwlog-smart.service /usr/local/src/minisforum-n5-it5571/hwlog/hwlog-smart.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now hwlog.timer hwlog-smart.timer
systemctl list-timers --all 'hwlog*'
```

The fast timer starts 30 seconds after boot and then approximately every
30 seconds; the SMART timer starts after 2 minutes and then approximately every
15 minutes. Check service results after they run:

```bash
systemctl status hwlog.timer hwlog-smart.timer
journalctl -u hwlog.service -u hwlog-smart.service -b
```

HTTP errors, connection failures and missing sensor warnings appear in the
journal. The services suppress routine systemd start and stop messages;
its output is logged at warning level so diagnostic messages remain visible.
To apply an updated service file to an existing installation, repeat the
installation command above and run `systemctl daemon-reload`. Avoid sharing
credentials or sensitive host information when requesting help.

## Collected data

- `fast`: `temperature`, `power` and `fan_rpm` from the configured
  `sensors -j` chip/label mappings; `memory` in bytes; `load` averages; and
  `disk_temp` for supported SATA disks.
- `smart`: `disk_smart` attributes and `disk_health` status for detected SATA
  and NVMe disks when available.
- `all` (the manual default): both groups.

The script discovers `sd*` and `nvme*` disks through `lsblk`. For non-NVMe
disks it passes `-n standby` to `smartctl` to avoid waking sleeping drives;
their readings may therefore be absent. Unsupported or unavailable SMART
attributes are also omitted. NVMe temperatures come from the configured
lm-sensors mappings, not the disk-temperature collection.

To stop collection without deleting data already stored in InfluxDB:

```bash
systemctl disable --now hwlog.timer hwlog-smart.timer
```
