# Blackview BV5300 Plus (MediaTek MT8788V) Porting Guide

This document details the adaptation of the `ios-sweet` architecture to the **Blackview BV5300 Plus** (rugged smartphone with MediaTek MT8788V / MT6771 SoC).

---

## 1. Hardware Architecture Overview

| Parameter | Qualcomm Snapdragon 732G (`sweet`) | Blackview BV5300 Plus (`bv5300plus`) |
| :--- | :--- | :--- |
| **SoC** | SM7150 (8nm) | MediaTek MT8788V (12nm FinFET) |
| **CPU Cluster 0** | 6x Kryo 470 Silver (Cortex-A55 @ 1.8 GHz) | 4x ARM Cortex-A53 @ 2.0 GHz |
| **CPU Cluster 1** | 2x Kryo 470 Gold (Cortex-A76 @ 2.3 GHz) | 4x ARM Cortex-A73 @ 2.0 GHz |
| **ARM ISA** | ARMv8.2-A (No PAC) | ARMv8.0-A (No PAC) |
| **DRAM Physical Base** | `0x80000000` (2.0 GB) | `0x40000000` (1.0 GB) |
| **RAM Capacity** | 6GB / 8GB | 8GB LPDDR4X |
| **GIC Type** | GICv3 (GICD `0x17a00000`, GICR `0x17a60000`) | GICv3 / GIC-500 (GICD `0x0c000000`, GICR `0x0c080000`) |
| **UART Port** | QUP/GENI UART @ `0x00a88000` | AP UART0 @ `0x11002000` (115200 8N1) |
| **Display Panel** | 1080 x 2400 AMOLED/IPS (4320 B stride) | 720 x 1560 IPS LCD (2880 B stride) |
| **Storage Subsystem**| UFS 2.2 (`qcom,ufshc` @ `0x01d84000`) | eMMC 5.1 (MSDC0 @ `0x11230000`) |
| **Touch Controller**| Goodix GT9896 / FT3518 (QUP I2C) | FocalTech FT8719 / Chipone ICNL9911 (MTK I2C0) |
| **Boot Chain** | ABL (EDK2 UEFI) | MediaTek LK (Little Kernel) via ATF BL31 |

---

## 2. Directory & File Modifications

The target port adds and modifies the following components in the repository:

### 2.1 Boot Shim (`shim/`)
* **[`platform.h`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/shim/platform.h)**: Unified hardware definitions for Qualcomm SM7150 and MediaTek MT8788V.
* **[`console.h`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/shim/console.h)** & **[`console.c`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/shim/console.c)**: Adapted to support 720x1560 resolution (`CON_SCALE=2`) and added hardware serial logging via MediaTek AP UART0 (`0x11002000`).
* **[`mmu.c`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/shim/mmu.c)**: Expanded L2 block mapping up to 12 GB to cover MT8788's 8 GB physical RAM (`0x40000000` - `0x240000000`) and peripheral MMIO blocks.
* **[`shim.c`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/shim/shim.c)**: Added MediaTek Watchdog reset (`0x10007000`), GIC-500 PPI 11 timer interrupt routing (`INTID 27`), and Cluster 0/1 MPIDR mapping for 4x A53 + 4x A73 cores.
* **[`build_bv5300plus.sh`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/shim/build_bv5300plus.sh)**: MediaTek-specific `mkbootimg` packager targeting physical base `0x40000000`.

### 2.2 Tools & Utilities (`tools/`)
* **[`mkadt_mt8788.py`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/tools/mkadt_mt8788.py)**: Generates the binary Apple Device Tree (ADT) spoofing iPhone X (`D22AP`) while defining MT8788 MMIO nodes, 8-core SMP layout, 720x1560 framebuffer, and MediaTek AP UART.
* **[`bv5300-root-tweaks.py`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/tools/bv5300-root-tweaks.py)**: Configures the iOS 16 HFS+ root image with WindowServer software rasterizer parameters, screen geometry preferences, and hardware watchdog neutering.

### 2.3 Kernel Patches (`xnu/patches/`)
* **[`0082-mt8788-bv5300plus-platform.patch`](file:///C:/Users/svetlinkata/.gemini/antigravity/scratch/ios-sweet/xnu/patches/0082-mt8788-bv5300plus-platform.patch)**: Adapts `SweetCPU.cpp` to accept MediaTek MPIDR formats (`Aff1: Cluster, Aff0: Core`) and sets panel dot pitch to 282 PPI in `SweetFramebuffer.cpp`.

---

## 3. End-to-End Build and Flashing Workflow

### Step 1: Generate the Apple Device Tree (ADT)
```bash
python3 tools/mkadt_mt8788.py shim/out_bv5300plus/bv5300plus.adt
```

### Step 2: Build the Shim and Package Boot Image
```bash
# Package with XNU kernel Mach-O and ADT
python3 tools/mkpayload.py \
    xnu/out/kernel.development.sweet \
    shim/out_bv5300plus/bv5300plus.adt \
    shim/out_bv5300plus/payload.bin \
    --cmdline 'debug=0x14e serial=0x11002000,115200 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30 sweetfb_native=1'

# Compile bootstrap shim and package into boot image
bash shim/build_bv5300plus.sh shim/out_bv5300plus/payload.bin
```

### Step 3: Prepare the iOS 16 Root Filesystem
```bash
# Extract and build the HFS+ container from iPhone X IPSW
tools/mkiosroot.sh OS.dmg SystemOS.dmg AppOS.dmg ios16-bv5300plus.img 16G

# Mount and apply Blackview BV5300 Plus customizations
sudo fsck.hfsplus -fy ios16-bv5300plus.img
sudo mount -t hfsplus -o loop,force ios16-bv5300plus.img /mnt/iosroot
sudo python3 tools/bv5300-root-tweaks.py /mnt/iosroot
sudo umount /mnt/iosroot

# Convert to sparse image for fastboot
img2simg ios16-bv5300plus.img ios16-bv5300plus.simg
```

### Step 4: Boot via Fastboot
Put the Blackview BV5300 Plus into fastboot mode (Power + Volume Up, then select Fastboot):

```bash
# Flash the tweaked iOS 16 userland into userdata
fastboot -S 512M flash userdata ios16-bv5300plus.simg

# Boot the custom XNU bootloader shim ephemerally (does NOT overwrite stock boot)
fastboot boot shim/out_bv5300plus/shim-boot-bv5300plus.img
```
