# ios-sweet: Blackview BV5300 Plus Edition

**Apple's iOS 16 & XNU Kernel running on the Blackview BV5300 Plus (MediaTek MT8788V / MT6771).**

This repository adapts the [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) architecture—originally built for Qualcomm Snapdragon 732G (`sweet`)—to the rugged **Blackview BV5300 Plus** powered by the **MediaTek MT8788V** octa-core processor (4x Cortex-A73 + 4x Cortex-A53).

On top of Apple's open-source XNU kernel (`xnu-8796`) runs the unmodified **iOS 16.7.16 (20H392)** userland from the iPhone X (`D22AP` / `iPhone10,3`): `launchd`, core system daemons, `backboardd`, and `SpringBoard`.

---

## Hardware Specifications: Blackview BV5300 Plus

| Component | Target Specification |
| :--- | :--- |
| **SoC / CPU** | MediaTek MT8788V (4x Cortex-A73 @ 2.0 GHz, 4x Cortex-A53 @ 2.0 GHz) |
| **Architecture** | ARM64 (aarch64, ARMv8.0-A, No PAC/BTI) |
| **GPU** | ARM Mali-G72 MP3 (CPU software rasterization via `ForceSoftwareOpenGL`) |
| **RAM / Storage**| 8 GB LPDDR4X / 128 GB eMMC 5.1 (MSDC0 @ `0x11230000`) |
| **Display Panel**| 6.1" IPS LCD, 720 × 1560 resolution, 32bpp, Stride = 2880 bytes (`@2x` scale) |
| **DRAM Physical Base** | `0x40000000` (1.0 GB mark) |
| **Interrupt Controller** | ARM GIC-500 / GICv3 (GICD: `0x0c000000`, GICR: `0x0c080000`, vtimer PPI `27`) |
| **Serial Debug UART** | MediaTek AP UART0 @ `0x11002000` (115200 8N1) |
| **Boot Chain** | Preloader $\rightarrow$ ATF BL31 $\rightarrow$ Little Kernel (LK) Header v2 |

---

## Architectural Comparison: Snapdragon 732G vs. MediaTek MT8788V

```
Qualcomm SM7150 (sweet):
  DRAM Base: 0x80000000 (2GB) | GICD: 0x17a00000 | UART: 0x00a88000 | 1080x2400 AMOLED | UFS 2.2

MediaTek MT8788V (BV5300 Plus):
  DRAM Base: 0x40000000 (1GB) | GICD: 0x0c000000 | UART: 0x11002000 | 720x1560 IPS LCD | eMMC 5.1
```

---

## Porting Modifications & Layout

### 1. Unified Bootstrap Shim (`shim/`)
* **`shim/platform.h`**: Hardware memory mapping, timer frequencies, and peripheral addresses conditionally compiled with `-DTARGET_BV5300PLUS=1`.
* **`shim/console.c` & `console.h`**: Adapted for 720×1560 geometry (`CON_SCALE=2`) with hardware serial mirrors over MediaTek AP UART0 (`0x11002000`).
* **`shim/mmu.c`**: 16KB-granule level-2 translation table expanded to 12 GB, covering MT8788's 8 GB physical RAM and MMIO regions.
* **`shim/shim.c`**: Dual-cluster MPIDR routing (`Aff1: Cluster, Aff0: Core`) for 4x A53 + 4x A73 cores; MediaTek watchdog software reset (`0x10007000`, key `0x1209`).
* **`shim/build_bv5300plus.sh`**: Packager generating MediaTek LK boot headers matching factory offsets:
  * `--base 0x40000000`
  * `--kernel_offset 0x00080000`
  * `--ramdisk_offset 0x15000000`
  * `--tags_offset 0x14000000`
  * `--pagesize 2048`

### 2. Device Tree Synthesis (`tools/mkadt_mt8788.py`)
Generates the Apple Device Tree (ADT) in Apple's binary format:
* Sets machine identity to `iPhone10,3` / `D22AP` (`chip-id: 0x8015`).
* Binds MediaTek GIC-500, UART0, eMMC host MSDC0, and 720x1560 display geometry.
* Configures Hactivation tokens for `mobileactivationd` bypass.

### 3. Userland Adaptations (`tools/bv5300-root-tweaks.py`)
* Disables `_PanicOnCrash` in `launchd.plist`.
* Sets `com.apple.WindowServer` to use CPU software rasterization (`ForceSoftwareOpenGL = True`).
* Disables missing cellular (`CommCenter`), Wi-Fi (`wifid`), Bluetooth, and thermal shutdown daemons.
* Bypasses iOS Setup Assistant (`SetupDone = True`).

### 4. XNU Kernel Patch (`xnu/patches/0082-mt8788-bv5300plus-platform.patch`)
* Updates `SweetCPU.cpp` to validate MediaTek cluster-based MPIDR identifiers (`Aff1 <= 1`, `Aff0 <= 3`).
* Adjusts panel dot pitch in `SweetFramebuffer.cpp` to 282 PPI for 6.1" display.

---

## Quick Start: Building and Booting

### Step 1: Synthesize the Device Tree (ADT)
```bash
python tools/mkadt_mt8788.py shim/out_bv5300plus/bv5300plus.adt
```

### Step 2: Build the Kernel
The kernel builds via GitHub Actions on macOS runners.
1. Push your changes to your fork:
   ```bash
   git push origin port-bv5300plus-mt8788
   ```
2. Trigger the `xnu` workflow on GitHub Actions.
3. Download the built `xnu-kernel` artifact to `xnu/out/kernel.development.sweet`.

### Step 3: Package Payload & Boot Image
```bash
python tools/mkpayload.py \
    xnu/out/kernel.development.sweet \
    shim/out_bv5300plus/bv5300plus.adt \
    shim/out_bv5300plus/payload.bin \
    --cmdline 'debug=0x14e serial=0x11002000,115200 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30 sweetfb_native=1'

bash shim/build_bv5300plus.sh shim/out_bv5300plus/payload.bin
```

### Step 4: Flash RootFS and Boot
With the Blackview BV5300 Plus in fastboot mode:
```bash
# Flash the tweaked iOS 16 userland into the userdata partition
fastboot -S 512M flash userdata ios16-bv5300plus.simg

# Ephemerally boot XNU (does not overwrite stock boot partition)
fastboot boot shim/out_bv5300plus/shim-boot-bv5300plus.img
```

---

## Current Status & Bring-up Horizon

| Subsystem | Status | Notes |
| :--- | :--- | :--- |
| **Bootloader Unlock** | **Done** | Confirmed unlocked (`unlocked: yes`) |
| **Factory DTB** | **Extracted** | Located at `dtb/bv5300plus_unpacked/dtb` |
| **Bootstrap Shim** | **Adapted** | MT8788 physical layout, MMU, UART, GIC-500 |
| **ADT Generator** | **Verified** | `mkadt_mt8788.py` outputs valid binary ADT |
| **SMP (8 Cores)** | **Patched** | Handles 4x A53 + 4x A73 cluster topology |
| **Display** | **Software** | CPU-driven simplefb copy at 720×1560 |
| **GPU Acceleration** | **Disabled** | Mali-G72 lacks Metal driver; runs CPU fallback |
| **Wireless / Audio** | **Disabled** | Cellular, Wi-Fi, audio daemons neutered |

---

## License & Credits
* Original `ios-sweet` implementation for Qualcomm SM7150 by [dipa-studio](https://github.com/dipa-studio/ios-sweet).
* Apple XNU kernel source code licensed under the Apple Public Source License (APSL 2.0).
* Porting and MediaTek MT8788V platform architecture adaptation by L1ght / Antigravity.
