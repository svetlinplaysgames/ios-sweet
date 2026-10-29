#!/usr/bin/env python3
"""Pack an Android boot image header v2 (pure Python, zero dependencies).

Compatible with AOSP mkbootimg header version 2.
"""
import argparse, hashlib, os, struct, sys

def pad(data, page_size):
    remainder = len(data) % page_size
    if remainder:
        data += b'\0' * (page_size - remainder)
    return data

def main():
    parser = argparse.ArgumentParser(description="Pack Android boot image v2")
    parser.add_argument('--kernel', required=True, help="Path to kernel")
    parser.add_argument('--ramdisk', required=True, help="Path to ramdisk")
    parser.add_argument('--dtb', help="Path to dtb")
    parser.add_argument('--output', '-o', required=True, help="Output boot.img")
    parser.add_argument('--base', type=lambda x: int(x, 0), default=0x40000000, help="Base physical address")
    parser.add_argument('--kernel_offset', type=lambda x: int(x, 0), default=0x00080000)
    parser.add_argument('--ramdisk_offset', type=lambda x: int(x, 0), default=0x15000000)
    parser.add_argument('--tags_offset', type=lambda x: int(x, 0), default=0x14000000)
    parser.add_argument('--dtb_offset', type=lambda x: int(x, 0), default=0x14000000)
    parser.add_argument('--pagesize', type=int, default=2048)
    parser.add_argument('--header_version', type=int, default=2)
    parser.add_argument('--os_version', default="16.7.16")
    parser.add_argument('--os_patch_level', default="2026-10")
    parser.add_argument('--cmdline', default="")

    args, _ = parser.parse_known_args()

    kernel = open(args.kernel, 'rb').read()
    ramdisk = open(args.ramdisk, 'rb').read() if args.ramdisk and os.path.exists(args.ramdisk) else b''
    dtb = open(args.dtb, 'rb').read() if args.dtb and os.path.exists(args.dtb) else b''

    kernel_addr = args.base + args.kernel_offset
    ramdisk_addr = args.base + args.ramdisk_offset
    tags_addr = args.base + args.tags_offset
    dtb_addr = args.base + args.dtb_offset

    # Parse OS version (major.minor.patch) into 32-bit field
    os_ver_val = 0
    try:
        parts = [int(p) for p in args.os_version.split('.')]
        if len(parts) >= 1: os_ver_val |= (parts[0] & 0x7f) << 25
        if len(parts) >= 2: os_ver_val |= (parts[1] & 0x7f) << 18
        if len(parts) >= 3: os_ver_val |= (parts[2] & 0x7f) << 11
    except Exception:
        os_ver_val = 0

    # Build Header (1660 bytes for v2)
    hdr = bytearray(1660)
    hdr[0:8] = b'ANDROID!'
    struct.pack_into('<10I', hdr, 8,
                     len(kernel),
                     kernel_addr,
                     len(ramdisk),
                     ramdisk_addr,
                     0,          # second_size
                     0,          # second_addr
                     tags_addr,
                     args.pagesize,
                     args.header_version,
                     os_ver_val)

    # cmdline (first 512 bytes)
    cmdline_bytes = args.cmdline.encode('utf-8')[:512]
    hdr[64:64+len(cmdline_bytes)] = cmdline_bytes

    # extra cmdline (next 1024 bytes) if > 512
    if len(args.cmdline.encode('utf-8')) > 512:
        extra = args.cmdline.encode('utf-8')[512:1536]
        hdr[608:608+len(extra)] = extra

    # SHA1 ID of kernel + ramdisk + dtb
    sha = hashlib.sha1()
    sha.update(kernel)
    sha.update(ramdisk)
    sha.update(dtb)
    hdr[576:576+20] = sha.digest()

    # v1 fields
    # recovery_dtbo_size (uint32), recovery_dtbo_offset (uint64), header_size (uint32)
    struct.pack_into('<IQI', hdr, 1632, 0, 0, 1660)

    # v2 fields
    # dtb_size (uint32), dtb_addr (uint64)
    struct.pack_into('<IQ', hdr, 1648, len(dtb), dtb_addr)

    # Pad header, kernel, ramdisk, dtb to pagesize
    out = pad(hdr, args.pagesize)
    out += pad(kernel, args.pagesize)
    out += pad(ramdisk, args.pagesize)
    if dtb:
        out += pad(dtb, args.pagesize)

    with open(args.output, 'wb') as f:
        f.write(out)

    print(f"[+] Successfully wrote {len(out)} bytes to {args.output}")

if __name__ == '__main__':
    main()
