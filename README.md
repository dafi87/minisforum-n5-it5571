# Minisforum N5 EC / IT5571 sensors for Proxmox VE

<p align="center">
  <img src="icons/minisforum-n5-it5571-512.png" width="256" alt="Minisforum N5 EC / IT5571 Driver">
</p>


`minisforum_n5_it5571` is a Linux hwmon driver for the Minisforum N5 family and
its ITE IT5571 EC. N5/F8NAA is hardware-validated, and the N5 Air/F8NAB sensor
build running BIOS 1.01 has now been hardware-validated on Proxmox in read-only
mode. The Python CLI reads temperatures and fan RPM in human readable or JSON
form for use in scripts.

## Features

- CPU, SSD and HDD fan RPM; PCIe RPM is unavailable.
- CPU and System temperatures; Board and Ambient on N5/F8NAA.
- DDR5 SPD5118 memory and Realtek r8169 PHY temperatures when available.
- JSON output for integration with scripts.

## Compatibility

| Device / DMI product | Mainboard | Status | Default mode |
|---|---|---|---|
| Minisforum N5 / `N5` | `F8NAA` | Hardware-validated (BIOS 1.04) | PWM enabled |
| Minisforum N5 Pro / `N5 PRO` | `F8NAA` | Experimental | Read-only sensors |
| Minisforum N5 Air / `N5A` or `N5 AIR` | `F8NAB` | Hardware-validated (BIOS 1.01, Proxmox; sensors only) | Read-only sensors |

The original N5/F8NAA was tested with BIOS 1.04. N5 Air/F8NAB sensor readings
and the Proxmox build have been hardware-validated with BIOS 1.01 in read-only
mode. PWM values have **not** been written or tested on N5 Air. DKMS builds the
module for matching installed kernels; kernel updates can still require driver fixes.

Unknown DMI pairs are rejected unless a developer uses
the read-only `force=1` override.

Using the same IT5571 chip does not imply drop-in compatibility. Vendors may use
different PMC commands, ports, EC RAM layouts, and fan wiring. The compatibility
list now includes two hardware-validated profiles: N5/F8NAA with PWM control,
and N5 Air/F8NAB with read-only sensor access on Proxmox. N5 Pro/F8NAA and N5
Air PWM writes still require physical testing one fan at a time before they can
be promoted.

Do not enable experimental PWM writes on the N5 Air while validating sensors.

## hwmon channels

| Node | Function |
|---|---|
| `pwm1`, `fan1_input` | CPU Fan |
| `pwm2`, `fan2_input` | SSD Fan |
| `pwm3`, `fan3_input` | HDD Fan Group |
| `pwm4`, `fan4_input` | PCIe Fan; RPM reports zero |
| `temp1_input` | CPU Temp |
| `temp2_input` | System Temp |
| `temp3_input` | Board Temp |
| `temp4_input` | Ambient Temp |

The CPU and System mappings, plus the N5 Air read-only sensor build, were
hardware-validated on N5 Air/F8NAB with BIOS 1.01 and Proxmox. Board and
Ambient are hidden on the N5 Air because their meanings are unverified. The
PCIe `fan4_input` zero is a placeholder, not a measured RPM; the CLI reports
it as unavailable.

## Installation

See the [Proxmox setup guide](docs/PROXMOX.md) for DKMS installation, validating
the readings, and configuring the module to load at boot. Once loaded:

```bash
python3 n5-sensors.py
python3 n5-sensors.py --json
```

For optional host-health logging to InfluxDB, see the
[hwlog installation guide](docs/HWLOG.md). There is no Proxmox web UI
integration.

## Disclaimer

This project is an independent community effort and is **not affiliated with,
endorsed by, or supported by Minisforum**. It contains unverified factors and is
provided "as is" without warranty of any kind. **Use at your own risk.** The
author accepts no liability for any direct or indirect loss — including
hardware damage, fan-stall overheating, or data loss — arising from the use of
this driver. See [DISCLAIMER.md](DISCLAIMER.md) for the full terms.

N5/F8NAA is validated for PWM and sensor operation. N5 Air/F8NAB is validated
for read-only sensor operation on BIOS 1.01 with Proxmox. N5 Air PWM writes have
not been tested. N5 Pro/F8NAA remains experimental; no compatibility guarantee
is made beyond the validated scopes above.

## Safety

- **Stop immediately** if a fan stops, runs unexpectedly, controls the wrong
  header, disappears, or any temperature becomes abnormal. Stop fan-control
  services and run `modprobe -r minisforum_n5_it5571`; reboot into BIOS control
  if unload fails.
- Never leave an experimental PWM test unattended.
- Do not use `force=1 experimental_write=1` on an unknown board as a normal
  installation method.
- Do not install a `.ko` built for a different kernel.
- Confirm the physical fan-to-zone mapping before changing PWM values.
- Assign each `pwmN` to one fan controller only.
- Module unload attempts to restore only channels it modified. A separate N5
  Air report found that CPU fan channels required a reboot after PWM writes;
  see the [Proxmox setup guide](docs/PROXMOX.md).

## License

The driver source is intended for release under GPL-2.0-only. The repository
must not redistribute vendor EC firmware or the confidential IT5571 datasheet.

## Credits

This repository is a fork of the original community work at
[ltdstudio/minisforum-n5-it5571](https://github.com/ltdstudio/minisforum-n5-it5571).
We credit its author and contributors for the original driver, reverse
engineering, documentation, and validation work.

## Support

When reporting a problem, include the Proxmox version, `uname -r`, BIOS version,
DMI board identity, `modinfo minisforum_n5_it5571`, and relevant `dmesg` output.
