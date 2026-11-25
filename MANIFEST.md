# Repository manifest

## `driver-prototype/`

- `minisforum_n5_it5571.c`: Linux hwmon driver source; N5 validated, N5 Pro/Air experimental.
- `Makefile`: external kernel-module build file.
- `dkms.conf`: DKMS module registration and automatic rebuild configuration.
- `README.md`: driver and channel notes.

The public module and hwmon name is `minisforum_n5_it5571`.

## `research-tools/`

- `n5_fan.c`: PMC/EC fan telemetry reader.
- `n5_pwm_diag.c`: PWM mapping and manual/automatic-mode diagnostic.
- `n5_i2ec_read.c`: read-only IT5571 I2EC register diagnostic.
- `ec_probe.c`: ACPI-style EC RAM read/write diagnostic; writes are dangerous.
- `sio_probe.c`: IT5571 Super I/O configuration-space diagnostic.

Only source is included. Temporary standalone binaries are omitted because they
can be rebuilt and may contain build-environment debug paths.

## Sensor reader and setup

- `n5-sensors.py`: read-only CLI with JSON output.
- `docs/PROXMOX.md`: Proxmox build, setup, and validation guide.
- `tests/test_n5_sensors.py`: focused CLI tests.

## `docs/research/`

- `N5-EC-PROBE-NOTES.zh-CN.md`: EC discovery notes.
- `N5-FAN-RESEARCH.zh-CN.md`: early fan-interface research report.
- `N5-PWM-RPM-REVERSE-ENGINEERING.zh-CN.md`: detailed PWM/RPM reverse-engineering log.
- `RESULTS.en.md` and `RESULTS.zh-CN.md`: historical N5/F8NAA validation results.

Host-specific SSH details have been replaced with placeholders.

`legacy-pcie-autofan/pcie-autofan.conf` is retained as requested; its former
controller is no longer included.

## `LICENSES/`

GPL-2.0 license material applicable to the prototype driver source. Individual
files retain their SPDX identifiers.

## Intentionally excluded

- Minisforum BIOS images and EC firmware binaries.
- Firmware disassemblies and other derived firmware dumps.
- The confidential ITE IT5571 datasheet and rendered pages.
- Linux source archives and extracted kernel trees.
- Zig/compiler caches, object files, kernel modules, temporary binaries, logs,
  and SSH records.
- Passwords, IP addresses, and local user paths.
- Third-party MCS51 disassembler copies; they are not required to build or use
  the driver and are not part of this project's authored source.
- Duplicate/stale publication-draft directories.
