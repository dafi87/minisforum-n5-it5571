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

## Install with DKMS

Run the installation and removal commands as root on the Proxmox host. Install
DKMS and the build tools, and verify that the running kernel's headers are
present:

```bash
apt install dkms build-essential
uname -r
ls -l "/lib/modules/$(uname -r)/build/Makefile"
```

If the header check fails, install the headers matching `uname -r`:

```bash
apt install "proxmox-headers-$(uname -r)"
```

For automatic rebuilds after future updates, also install the header metapackage
for the kernel series you follow. For the reported 7.0 series:

```bash
apt-cache depends proxmox-headers-7.0
apt install proxmox-headers-7.0
```

Check APT's proposed changes before accepting: the metapackage may bring in
newer headers and kernel packages. `proxmox-default-headers` instead tracks the
default kernel series; choose the metapackage matching your update policy.

From the repository root, copy a clean source snapshot to DKMS and install it
for the running kernel:

```bash
cd driver-prototype
mkdir /usr/src/minisforum_n5_it5571-0.2.0 &&
  install -m 0644 dkms.conf Makefile minisforum_n5_it5571.c /usr/src/minisforum_n5_it5571-0.2.0/ &&
  dkms add -m minisforum_n5_it5571 -v 0.2.0 &&
  dkms install -m minisforum_n5_it5571 -v 0.2.0 -k "$(uname -r)"
```

The `mkdir` intentionally fails rather than overwrite an existing source
snapshot. If DKMS installation fails after registration, resolve the reported
error and rerun the `dkms install` command; consult `dkms status` and
`/var/lib/dkms/minisforum_n5_it5571/0.2.0/build/make.log` for details.

If the module is already loaded from an earlier manual test, unload it first
while still in read-only mode:

```bash
rmmod minisforum_n5_it5571
```

Then test the DKMS-installed module, without enabling PWM writes:

```bash
modprobe minisforum_n5_it5571
dkms status minisforum_n5_it5571/0.2.0
modinfo -n minisforum_n5_it5571
modinfo -F vermagic minisforum_n5_it5571
dmesg | tail -n 50
cd ..
python3 ./n5-sensors.py
python3 ./n5-sensors.py --json
```

Confirm DKMS reports the module installed for the running kernel, `modinfo -n`
points to the DKMS-installed module, and the first word of vermagic matches
`uname -r`. A successful `modprobe` does not necessarily mean the device bound:
check the driver's messages and CLI output. If a port is busy, do not force
access or disable an existing EC driver; investigate the conflict first. An
empty `/proc/ioports` grep alone does not establish EC compatibility or absence
of contention. Compare readings against BIOS and other trusted sensors, and
confirm physical fan/channel mappings before relying on them.

Secure Boot may reject a module if its signing key is not enrolled. Follow the
host's signing and key-enrollment policy; do not disable Secure Boot to load it.

Only after verifying the readings, configure loading at boot:

```bash
echo minisforum_n5_it5571 | tee /etc/modules-load.d/minisforum-n5-it5571.conf
```

DKMS attempts to build and install this version for new kernels automatically
when their matching headers are installed. Check `dkms status` and the package
installation output after kernel updates; a missing header, changed kernel API,
or signing failure can prevent the module from loading. Keep a working kernel
available for rollback. The source in `/usr/src/minisforum_n5_it5571-0.2.0` is
a snapshot: changes in the checkout do not update it. Use a new DKMS version
for a source update; do not overwrite an installed version in place.

To uninstall, remove the modules-load configuration, unload the driver, and
remove its DKMS registration:

```bash
rm /etc/modules-load.d/minisforum-n5-it5571.conf
modprobe -r minisforum_n5_it5571
dkms remove -m minisforum_n5_it5571 -v 0.2.0 --all
```

DKMS may restore a previously installed same-named module when removing its
version. Check `dkms status` and `modinfo -n minisforum_n5_it5571` before
assuming no module remains; the source snapshot may also remain under `/usr/src`.

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
