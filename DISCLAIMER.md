# DISCLAIMER

The `minisforum_n5_it5571` driver and all materials in this repository
(documents, scripts, firmware analysis, measurements) are the result of an
**independent community exploration** by ltdstudio. This project is:

- **NOT affiliated with, endorsed by, or supported by Minisforum** (Shenzhen
  Meigao Electronic Equipment Co., Ltd.).
- **NOT an official product.** Minisforum provides no warranty, support, or
  liability for this project.

This is an early community driver. It was tested on the original author's N5 / F8NAA
with BIOS 1.04. N5 Air / F8NAB sensor readings and the Proxmox build have also
been hardware-validated with BIOS 1.01 in read-only mode; PWM values were not
written or tested on N5 Air. It **contains
unverified factors**: hardware batches, BIOS/EC firmware versions, kernel
versions, and third-party software combinations may behave differently.

**THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.**

By installing or using this driver you agree that:

1. You have verified the exact DMI profile. N5/F8NAA is validated; N5
   Pro/F8NAA and N5 Air/F8NAB are experimental, read-only by default, and
   require explicit opt-in before PWM writes are exposed.
2. You assign each fan channel (`pwm1`–`pwm4`) to exactly one controller to
   avoid conflicting control loops.
3. You rebuild and install a kernel-matched module after every kernel update.
4. You accept full responsibility for any outcome of using this driver.

If you do not agree with these terms, do not install or use this software.

