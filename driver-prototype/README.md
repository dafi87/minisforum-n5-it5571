# Minisforum N5 family / IT5571 hwmon driver

This driver exposes the Minisforum N5 IT5571 fan controller and EC
temperatures through the standard Linux hwmon ABI. For DKMS installation and
kernel updates, see the [Proxmox setup guide](../docs/PROXMOX.md).

N5/F8NAA is validated. N5 Air/F8NAB sensor readings and the Proxmox build are
hardware-validated with BIOS 1.01 in read-only mode. N5 Air PWM values have not
been written or tested. N5 Pro/F8NAA remains experimental and loads in
read-only sensor mode unless `experimental_write=1` is explicitly set.
If a fan stops, runs unexpectedly, maps to the wrong channel, or temperatures
become abnormal, stop immediately and unload the module.

## Channel map

| hwmon node | N5 function | Feedback |
|---|---|---|
| `pwm1`, `fan1_input` | CPU fan | TACH1 |
| `pwm2`, `fan2_input` | SSD fan | TACH2 |
| `pwm3`, `fan3_input` | HDD fan group | TACH3 |
| `pwm4`, `fan4_input` | PCIe fan | no tach; reads 0 RPM |
| `temp1_input` | CPU Temp | EC 0x09 |
| `temp2_input` | System Temp | EC 0x04 |
| `temp3_input` | Board Temp | EC 0x05 |
| `temp4_input` | Ambient Temp | EC 0x06 |

On N5 Air, `temp3_input` and `temp4_input` and their labels are hidden because
their meanings are unverified. The CPU and System mappings remain experimental.

`pwmN_enable=1` selects manual control and `pwmN_enable=2` restores the native
EC/BIOS automatic curve. Module removal attempts to restore channels that the module
actually attempted to modify, but a separate N5 Air report found that CPU fan
channels required a reboot after PWM writes; see the
[Proxmox setup guide](../docs/PROXMOX.md).

The PCIe channel deliberately exports `fan4_input=0` because the original N5
firmware has no fourth tachometer signal. The sensor CLI reports it as
unavailable. N5 Air CPU and System sensor mappings and the N5 Air Proxmox build
are validated only for read-only operation on BIOS 1.01; PWM writes remain untested.
