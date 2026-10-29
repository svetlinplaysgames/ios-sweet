#!/bin/bash
# Build the shim for Blackview BV5300 Plus (MediaTek MT8788V / MT6771)
set -euo pipefail
cd "$(dirname "$0")"

CC=${CROSS_COMPILE:-aarch64-linux-gnu-}gcc
OBJCOPY=${CROSS_COMPILE:-aarch64-linux-gnu-}objcopy
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra -DTARGET_BV5300PLUS=1"

mkdir -p out_bv5300plus
echo "[*] Compiling bootstrap shim for Blackview BV5300 Plus (MT8788V)..."

for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c $f -o out_bv5300plus/${f%.*}.o
done

# Verify no absolute relocations in C objects
abs=$(${CROSS_COMPILE:-aarch64-linux-gnu-}readelf -r out_bv5300plus/shim.o out_bv5300plus/console.o out_bv5300plus/mmu.o out_bv5300plus/fdt.o out_bv5300plus/loader.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }

$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	out_bv5300plus/start.o out_bv5300plus/shim.o out_bv5300plus/console.o out_bv5300plus/mmu.o out_bv5300plus/fdt.o out_bv5300plus/loader.o -o out_bv5300plus/shim.elf

$OBJCOPY -O binary out_bv5300plus/shim.elf out_bv5300plus/Image

# Pad to image_size so .bss/stacks exist as zeroed bytes in memory
size=$(${CROSS_COMPILE:-aarch64-linux-gnu-}nm out_bv5300plus/shim.elf | awk '$3=="_end"{print strtonum("0x"$1)}')
truncate -s "$size" out_bv5300plus/Image

# Ramdisk packaging
if [ -n "${1:-}" ]; then
	cp "$1" out_bv5300plus/ramdisk.bin
else
	(cd out_bv5300plus && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi

DTB_PATH="../dtb/bv5300plus_unpacked/dtb"
DTB_ARG=""
if [ -f "$DTB_PATH" ]; then
	DTB_ARG="--dtb $DTB_PATH --dtb_offset 0x14000000"
fi

PACKER="python3 ../tools/pack_bootv2.py"
if command -v mkbootimg &>/dev/null; then
	PACKER="mkbootimg"
fi

echo "[*] Packaging Android boot image for MediaTek LK fastboot matching factory offsets..."
$PACKER \
	--header_version 2 \
	--kernel out_bv5300plus/Image \
	--ramdisk out_bv5300plus/ramdisk.bin \
	$DTB_ARG \
	--base 0x40000000 \
	--kernel_offset 0x00080000 \
	--ramdisk_offset 0x15000000 \
	--tags_offset 0x14000000 \
	--pagesize 2048 \
	--os_version 16.7.16 \
	--os_patch_level 2026-10 \
	--cmdline "serial=0x11002000,115200 console=tty0 bootopt=64S3,32N2,64N2" \
	-o out_bv5300plus/shim-boot-bv5300plus.img

echo "[+] Successfully generated: out_bv5300plus/shim-boot-bv5300plus.img"
