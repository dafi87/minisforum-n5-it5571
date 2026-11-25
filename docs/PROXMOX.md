# Proxmox VE: N5 sensor readings

The N5 Air (`N5A` / `F8NAB`) is already recognized by the driver, but its
registers, channel labels, and readings are **experimental**, inferred from the
N5/F8NAA, not verified on N5 Air hardware. Proxmox builds have not been
hardware-validated. The driver accesses EC I/O ports even in read-only mode;
read-only means it does not change fan settings, not that EC access is risk-free.
See [the disclaimer](../DISCLAIMER.md). Stop and unload it if fans or
temperatures behave unexpectedly. Do not enable `experimental_write` or run
other EC probing/control tools concurrently.

On N5 Air the driver hides the unverified Board and Ambient temperatures. CPU
and System mappings remain experimental. A [separate single-device N5 Air
report](https://github.com/outlawpractice/minisforum-n5-fan-control#fail-safe)
found that CPU fan channels did not return to firmware control after PWM
writes until reboot; do not assume restoring automatic mode works on this
profile. This does not apply to a read-only session that has made no PWM writes.

Build the module on the Proxmox host against the headers for its running
kernel. The following assumes `make`, a C compiler, Python 3, and matching
headers are already installed:

```bash
uname -r
ls -ld "/lib/modules/$(uname -r)/build"
cd driver-prototype
make
modinfo -F vermagic ./minisforum_n5_it5571.ko
```

The first word of the vermagic must match `uname -r`. If build tools or headers
are missing, install the distribution's matching packages before building.
Secure Boot may reject an unsigned module; do not bypass the host's security
policy to load it.

Test manually, without enabling PWM writes:

```bash
sudo insmod ./minisforum_n5_it5571.ko
dmesg | tail -n 50
cd ..
python3 ./n5-sensors.py
python3 ./n5-sensors.py --json
```

A successful `insmod` does not necessarily mean the device bound: check the
driver's messages and the CLI output. If a port is busy, do not force access or
disable an existing EC driver; investigate the conflict first. An empty
`/proc/ioports` grep alone does not establish that the EC is compatible or
uncontended. Compare readings against BIOS and other trusted sensors, and
confirm physical fan/channel mappings before relying on them.

Once tested, install the module for the current kernel and arrange to load it
at boot:

```bash
cd driver-prototype
sudo make -C "/lib/modules/$(uname -r)/build" M="$PWD" modules_install
sudo depmod -a
echo minisforum_n5_it5571 | sudo tee /etc/modules-load.d/minisforum-n5-it5571.conf
```

Rebuild and reinstall against the new running kernel after each kernel update.
To stop using the driver, remove that modules-load configuration and run
`sudo modprobe -r minisforum_n5_it5571`; reboot if it cannot be unloaded.

## CLI and scripts

The CLI uses Python's standard library and discovers the driver by hwmon name,
not by a changing `hwmonN` number. It needs read access to sysfs; it does not
need root when those files are readable. `--json` produces one JSON object:

```json
{"temperatures_c":{"cpu":25.0,"system":22.0},"fans_rpm":{"cpu":0,"ssd":2234,"hdd":1244,"pcie":null},"memory_temperatures_c":{"0-0051":22.75},"nic_temperatures_c":{"r8169_0_200:00":26.0,"r8169_0_300:00":27.5}}
```

Temperatures are Celsius and fan speeds are integer RPM. Keys describe the
driver's **unverified N5 Air mapping**. The CLI identifies N5 Air by its DMI
product and board names and omits `board` and `ambient`, even with an older
driver; other profiles still report them. Rebuild and reload the module to hide
their hwmon files. `pcie` is always `null`: the existing
driver reports `fan4_input` as zero without tachometer feedback, not a measured
zero RPM. A temperature reported by the driver as unavailable is `null`, with a
warning on stderr. Other read errors or a missing/ambiguous driver produce an
error on stderr, no JSON, and a nonzero exit status. Check the exit status and
omit null fields when sending data to InfluxDB; this tool does not write to a
database or modify the Proxmox web UI.

When present, `memory_temperatures_c` contains SPD5118 memory sensors keyed by
their I2C device names, and `nic_temperatures_c` contains Realtek r8169 PHY
sensors keyed by their hwmon names. These identifiers do not depend on the
`hwmonN` number but can change if bus enumeration or hardware changes. Each
group is omitted when no matching sensor is present; if a detected sensor
cannot be read, the command fails instead of silently omitting it. These sensors
come from their own kernel drivers and do not require the N5 module to expose
them, though the CLI still requires the N5 module.

For troubleshooting, collect `uname -r`, the DMI product and board names,
`modinfo` output, relevant `dmesg` messages, and the CLI output. Avoid sharing
credentials or other sensitive host information.
