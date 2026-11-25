# Proxmox VE: N5 sensor readings

The N5 Air (`N5A` / `F8NAB`) is already recognized by the driver, but its
registers, channel labels, and readings are **experimental**, inferred from the
N5/F8NAA, not verified on N5 Air hardware. Proxmox builds have not been
hardware-validated. The driver accesses EC I/O ports even in read-only mode;
read-only means it does not change fan settings, not that EC access is risk-free.
See [the disclaimer](../DISCLAIMER.md). Stop and unload it if fans or
temperatures behave unexpectedly. Do not enable `experimental_write` or run
other EC probing/control tools concurrently.

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
{"temperatures_c":{"cpu":42.0,"system":33.0,"board":30.0,"ambient":25.0},"fans_rpm":{"cpu":1200,"ssd":900,"hdd":850,"pcie":null}}
```

Temperatures are Celsius and fan speeds are integer RPM. Keys describe the
driver's **unverified N5 Air mapping**. `pcie` is always `null`: the existing
driver reports `fan4_input` as zero without tachometer feedback, not a measured
zero RPM. A temperature reported by the driver as unavailable is `null`, with a
warning on stderr. Other read errors or a missing/ambiguous driver produce an
error on stderr, no JSON, and a nonzero exit status. Check the exit status and
omit null fields when sending data to InfluxDB; this tool does not write to a
database or modify the Proxmox web UI.

For troubleshooting, collect `uname -r`, the DMI product and board names,
`modinfo` output, relevant `dmesg` messages, and the CLI output. Avoid sharing
credentials or other sensitive host information.
