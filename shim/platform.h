#pragma once
#include <stdint.h>

#if defined(TARGET_BV5300PLUS) || defined(TARGET_MT8788)

/* ============================================================================
 * Target: Blackview BV5300 Plus (MediaTek MT8788V / MT6771 Platform)
 * ============================================================================ */
#define PLATFORM_NAME           "Blackview BV5300 Plus (MT8788V)"
#define TARGET_ID_STRING        "MT8788XN"

/* Physical Memory Map */
#define DRAM_PHYS_BASE          0x40000000UL    /* MediaTek 1.0GB RAM base */
#define DRAM_PHYS_SIZE          0x200000000ULL  /* 8GB physical DDR */

/* Display / Framebuffer (MediaTek LK Continuous Splash Carveout) */
#define FB_BASE                 0x5e000000UL
#define FB_PHYS                 FB_BASE
#define FB_W                    720
#define FB_H                    1560
#define FB_STRIDE               (FB_W * 4)      /* 2880 bytes */
#define CON_SCALE               2               /* 2x font scale for 720p density */

/* Interrupt Controller (ARM GIC-500 / GICv3) */
#define GICD_BASE               0x0c000000UL
#define GICR_BASE               0x0c080000UL
#define GICR_SIZE               0x100000UL
#define GICR_PE_SIZE            0x20000UL
#define VTIMER_INTID            27              /* Standard ARM PPI 11 for vtimer */
#define PTIMER_INTID            30              /* Standard ARM PPI 14 for ptimer */
#define SGI_INTID               1

/* Clocks & Timers */
#define TIMEBASE_FREQ           13000000UL      /* 13MHz / 26MHz generic timer crystal */

/* Serial UART */
#define UART_BASE               0x11002000UL    /* MediaTek AP UART0 (8250 compatible) */
#define UART_RBR                (UART_BASE + 0x00)
#define UART_THR                (UART_BASE + 0x00)
#define UART_LSR                (UART_BASE + 0x14)
#define UART_LSR_THRE           0x20            /* Transmit Holding Register Empty */

/* Watchdog / Reset */
#define MTK_WDT_BASE            0x10007000UL
#define MTK_WDT_MODE            (MTK_WDT_BASE + 0x00)
#define MTK_WDT_RESTART         (MTK_WDT_BASE + 0x08)
#define MTK_WDT_SWRST           (MTK_WDT_BASE + 0x14)
#define MTK_WDT_SWRST_KEY       0x1209

/* Storage (eMMC 5.1 Host MSDC0) */
#define MSDC0_BASE              0x11230000UL
#define HAS_UFS                 0

/* Topology */
#define NR_CPUS                 8

#else

/* ============================================================================
 * Target: Xiaomi Redmi Note 10 Pro (Qualcomm Snapdragon 732G / SM7150 "sweet")
 * ============================================================================ */
#define PLATFORM_NAME           "Xiaomi Redmi Note 10 Pro (SM7150 'sweet')"
#define TARGET_ID_STRING        "SWEETXNU"

#define DRAM_PHYS_BASE          0x80000000UL
#define DRAM_PHYS_SIZE          0x180000000ULL  /* Up to 6/8GB */

#define FB_BASE                 0x9c000000UL
#define FB_PHYS                 FB_BASE
#define FB_W                    1080
#define FB_H                    2400
#define FB_STRIDE               (FB_W * 4)      /* 4320 bytes */
#define CON_SCALE               3               /* 3x font scale for 1080p density */

#define GICD_BASE               0x17a00000UL
#define GICR_BASE               0x17a60000UL
#define GICR_SIZE               0x100000UL
#define GICR_PE_SIZE            0x20000UL
#define VTIMER_INTID            19              /* Qualcomm DT custom PPI */
#define PTIMER_INTID            18
#define SGI_INTID               1

#define TIMEBASE_FREQ           19200000UL

#define IMEM_RESTART_REASON     0x146aa65cUL
#define RESTART_BOOTLOADER      0x77665500U
#define PSHOLD                  0x0c264000UL

#define UFS_BASE                0x01d84000UL
#define HAS_UFS                 1

#define NR_CPUS                 8

#endif
