#!/usr/bin/env python3
"""Build the Apple Device Tree (ADT) for Blackview BV5300 Plus (MediaTek MT8788V / MT6771).

Usage:
  mkadt_mt8788.py OUT.adt [--dump]
"""
import hashlib, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt

# ---------------------------------------------------------------------------
# MediaTek MT8788V Platform Parameters (Blackview BV5300 Plus)
# ---------------------------------------------------------------------------
# Physical RAM base starts at 1GB on MediaTek platforms
PHYS_BASE = 0x40000000
# 8GB total DDR: reserve upper carve-outs for LK/TZ, expose ~7.5GB to XNU
MEM_SIZE = 0x1e0000000
PANIC_LOG_SIZE = 0x100000

# MMIO Subsystems
SOC_BASE = 0x0c000000
GICD, GICD_SIZE = 0x0c000000, 0x10000
GICR, GICR_SIZE = 0x0c080000, 0x100000
UART0, UART0_SIZE = 0x11002000, 0x1000
MSDC0, MSDC0_SIZE = 0x11230000, 0x1000  # eMMC 5.1 Host Controller
I2C0, I2C0_SIZE = 0x11007000, 0x1000

# Framebuffer: MediaTek LK continuous splash carveout (720 x 1560 IPS LCD)
FB_BASE, FB_SIZE = 0x5e000000, 0x00500000  # ~5.2 MB
FB_W, FB_H = 720, 1560
FB_STRIDE = FB_W * 4  # 2880 bytes

TIMEBASE = 13000000     # MediaTek 13 MHz / 26 MHz generic timer base
VTIMER_INTID = 27       # Standard ARM GIC PPI 11 for vtimer (INTID 27)

BV5300_ECID = 0x4256353300000001  # 'BV53' + 1 synthetic ECID
BOOT_MANIFEST_HASH = hashlib.sha384(b'bv5300plus boot manifest').digest()

D22AP_ADT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../research/ipsw-x/d22ap.adt')


def d22ap_product(path=D22AP_ADT):
    """Extract /product properties from iPhone X device tree if present."""
    if not os.path.exists(path):
        return None
    root, _ = adt.parse(open(path, 'rb').read())
    for c in root.children:
        if dict((k, v) for k, f, v in c.props).get('name') == b'product\0':
            return [(k, v) for k, f, v in c.props if not f and k not in ('name', 'AAPL,phandle')]
    return None


u32 = lambda *v: struct.pack('<%dI' % len(v), *v)
u64 = lambda *v: struct.pack('<%dQ' % len(v), *v)
cstr = lambda s: s.encode() + b'\0'


def node(name, props=(), children=()):
    n = adt.Node()
    n.props = [('name', 0, cstr(name))] + [(k, 0, v) for k, v in props]
    n.children = list(children)
    return n


def build_adt(seed=None):
    phys_base, mem_size = PHYS_BASE, MEM_SIZE
    panic_base = phys_base + mem_size - PANIC_LOG_SIZE
    mem_size -= PANIC_LOG_SIZE

    seed = seed if seed is not None else os.urandom(64)
    phandle = iter(range(1, 1000))
    ph = lambda: ('AAPL,phandle', u32(next(phandle)))

    chosen = node('chosen', [
        ph(),
        ('dram-base', u64(phys_base)),
        ('dram-size', u64(mem_size)),
        ('random-seed', seed),
        ('debug-enabled', u32(1)),
        ('embedded-panic-log-size', u32(PANIC_LOG_SIZE)),
        ('firmware-version', cstr('bv5300plus-shim')),
        ('system-firmware-version', cstr('bv5300plus-shim')),
        ('boot-manifest-hash', BOOT_MANIFEST_HASH),
        ('crypto-hash-method', cstr('sha2-384')),
        # 720x1560 display: @2x scale (360x780 points)
        ('display-scale', u32(2)),
        ('unique-chip-id', struct.pack('<Q', BV5300_ECID)),
        ('chip-id', u32(0x8015)),  # A11 Bionic identifier for D22AP userland
        # Hactivation security mode tokens
        ('certificate-production-status', u32(0)),
        ('effective-production-status-ap', u32(0)),
        ('certificate-security-mode', u32(1)),
        ('effective-security-mode-sep', u32(1)),
    ], [
        node('memory-map', [ph()]),
        node('asmb', [ph(), ('lp-sip0', u64(0x6f)), ('lp-sip1', u32(1))])
    ])

    # ---------------------------------------------------------------------------
    # MediaTek MT8788V SMP Topology (8 cores: 4x A53 + 4x A73)
    # ---------------------------------------------------------------------------
    cpu_nodes = []
    for core in range(8):
        is_a73 = core >= 4
        # Cluster 0 (Cores 0-3): MPIDR 0x000..0x003
        # Cluster 1 (Cores 4-7): MPIDR 0x100..0x103
        mpidr = ((core - 4) | (1 << 8)) if is_a73 else core
        cpu_nodes.append(node(f'cpu{core}', [
            ph(),
            ('device_type', cstr('cpu')),
            ('compatible', cstr('arm,cortex-a73' if is_a73 else 'arm,cortex-a53') + cstr('ARM,v8')),
            ('reg', u32(mpidr)),
            ('cpu-id', u32(core)),
            ('cluster-id', u32(1 if is_a73 else 0)),
            ('cluster-type', u32(0)),
            ('die-cluster-id', u32(0)),
            ('cluster-core-id', u32(core - 4 if is_a73 else core)),
            ('l2-cache-id', u32(core)),
            ('l3-cache-id', u32(0)),
            ('state', cstr('running' if core == 0 else 'stopped')),
            ('timebase-frequency', u32(TIMEBASE)),
            ('clock-frequency', u32(1990000000)),
            ('bus-frequency', u32(100000000)),
            ('memory-frequency', u32(1600000000)),
            ('peripheral-frequency', u32(TIMEBASE)),
            ('fixed-frequency', u32(TIMEBASE)),
        ]))
    cpus = node('cpus', [ph(), ('#address-cells', u32(1)), ('#size-cells', u32(0))], cpu_nodes)

    # ---------------------------------------------------------------------------
    # Interrupt Controller (ARM GIC-500 / GICv3)
    # ---------------------------------------------------------------------------
    gic = node('gic', [
        ph(),
        ('compatible', cstr('arm,gic-v3')),
        ('interrupt-controller', b''),
        ('virtual-timer-intid', u32(VTIMER_INTID)),
        ('reg', u64(GICD - SOC_BASE, GICD_SIZE, GICR - SOC_BASE, GICR_SIZE)),
    ])

    # ---------------------------------------------------------------------------
    # Serial UART (MediaTek AP UART0 @ 0x11002000)
    # ---------------------------------------------------------------------------
    uart0 = node('uart0', [
        ph(),
        ('compatible', cstr('mediatek,mt6771-uart') + cstr('mediatek,uart') + cstr('apple,uart-16550')),
        ('reg', u64(UART0 - SOC_BASE, UART0_SIZE)),
        ('interrupts', u32(123)),
        ('clock-frequency', u32(26000000)),
    ])

    # ---------------------------------------------------------------------------
    # ARM-IO Subsystem
    # ---------------------------------------------------------------------------
    arm_io = node('arm-io', [
        ph(),
        ('device_type', cstr('mtk-io')),
        ('compatible', cstr('mt8788-io') + cstr('arm-io')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
        ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE)),
    ], [
        gic,
        uart0,
        node('wdt', [ph(), ('no-pmu', u32(1))]),
        node('disp0', [
            ph(),
            ('device_type', cstr('display-subsystem')),
            ('compatible', cstr('mediatek,display') + cstr('apple,display-pipe')),
            ('canvas-width', u32(FB_W)),
            ('canvas-height', u32(FB_H)),
        ])
    ])

    # ---------------------------------------------------------------------------
    # Framebuffer Console
    # ---------------------------------------------------------------------------
    fbcon = node('mtk-fbcon', [
        ph(),
        ('reg', u64(FB_BASE, FB_SIZE)),
        ('width', u32(FB_W)),
        ('height', u32(FB_H)),
        ('stride', u32(FB_STRIDE)),
    ])

    # ---------------------------------------------------------------------------
    # Storage Host: eMMC 5.1 (MSDC0)
    # ---------------------------------------------------------------------------
    msdc0 = node('mtk-msdc0', [
        ph(),
        ('compatible', cstr('mediatek,mt8788-msdc') + cstr('mediatek,mt6771-mmc')),
        ('reg', u64(MSDC0, MSDC0_SIZE)),
    ])

    # ---------------------------------------------------------------------------
    # Touch Controller: Chipone / FocalTech on MTK I2C0
    # ---------------------------------------------------------------------------
    touch = node('touchscreen', [
        ph(),
        ('compatible', cstr('focaltech,ft8719') + cstr('chipone,icnl9911')),
        ('touchscreen-size-x', u32(FB_W)),
        ('touchscreen-size-y', u32(FB_H)),
        ('apple,hid-transport', cstr('i2c')),
    ])

    defaults = node('defaults', [ph(), ('no-effaceable-storage', u32(1))])

    # Physical Buttons: Vol+, Vol-, Power
    buttons = node('buttons', [
        ph(),
        ('button-names', cstr('volup') + cstr('voldown') + cstr('hold')),
        ('home-button-type', u32(2)),  # iPhone X gesture navigation
        ('opposed-power-vol-buttons', u32(1)),
    ])

    product_props = d22ap_product()
    product = [node('product', [ph()] + product_props)] if product_props else []

    pram = node('pram', [ph(), ('reg', u64(panic_base) + u64(PANIC_LOG_SIZE))])

    return node('device-tree', [
        ph(),
        ('compatible', cstr('D22AP') + cstr('iPhone10,3') + cstr('blackview,bv5300plus') + cstr('mediatek,mt8788') + cstr('AppleARM')),
        ('model', cstr('iPhone10,3')),
        ('target-type', cstr('D22')),
        ('target-sub-type', cstr('D22AP')),
        ('manufacturer', cstr('Apple Inc.')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [chosen, defaults, cpus, arm_io, fbcon, msdc0, touch, buttons, pram] + product)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} OUT.adt [--dump]")
        sys.exit(1)

    out_path = sys.argv[1]
    root = build_adt()
    blob = adt.serialize(root)
    with open(out_path, 'wb') as f:
        f.write(blob)

    if '--dump' in sys.argv:
        adt.dump(adt.parse(blob)[0])

    print(f"[+] Successfully wrote {len(blob)} bytes to {out_path}", file=sys.stderr)
