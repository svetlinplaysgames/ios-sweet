/*
 * Unified boot shim entry: arm64 Linux Image header.
 * Supports:
 *   - Qualcomm SM7150 (ABL)
 *   - MediaTek MT8788V / MT6771 (LK)
 */
	.section .text.head, "ax"
	.globl _head
_head:
	b	_start			/* code0 */
	.long	0			/* code1 */
#if defined(TARGET_BV5300PLUS) || defined(TARGET_MT8788)
	.quad	0x80000			/* text_offset: 0x80000 on MediaTek MT8788 */
#else
	.quad	0			/* text_offset */
#endif
	.quad	_end			/* image_size (linked at 0) */
	.quad	0xa			/* flags: LE, 4K pages, place anywhere */
	.quad	0			/* res2 */
	.quad	0			/* res3 */
	.quad	0			/* res4 */
	.ascii	"ARM\x64"		/* magic */
	.long	0			/* res5 (PE offset) */

	.text
	.globl _start
_start:
	/* ---- Detect EL; drop EL2->EL1 if MediaTek ATF delivered us at EL2 ---- */
	mrs	x1, CurrentEL
	lsr	x1, x1, #2
	cmp	x1, #2
	b.ne	_in_el1

	/* Running at EL2: set up EL1 as AArch64, then eret down */
	mov	x1, #(1 << 31)		/* HCR_EL2.RW = 1 (EL1 is AArch64) */
	msr	hcr_el2, x1
	msr	sctlr_el1, xzr		/* reset value: MMU/D-cache off */
	mov	x1, #0x3c5		/* SPSR_EL2: EL1h, DAIF all masked */
	msr	spsr_el2, x1
	adr	x1, _in_el1
	msr	elr_el2, x1
	/* x0 still holds DTB pointer */
	isb
	eret

_in_el1:
	msr	daifset, #0xf
	mov	x19, x0			/* DTB pointer from bootloader */
	msr	spsel, #1
	adr	x1, _stack_top
	mov	sp, x1
	adr	x1, vectors
	msr	vbar_el1, x1
	isb
	/* zero .bss */
	adr	x1, _bss_start
	adr	x2, _bss_end
1:	cmp	x1, x2
	b.hs	2f
	str	xzr, [x1], #8
	b	1b
2:	mov	x0, x19
	bl	shim_main
3:	wfe
	b	3b

/* PSCI CPU_ON target. x0 = context id = cpu index (1..7). */
	.globl secondary_entry
secondary_entry:
	/* Drop EL2->EL1 for secondary CPUs too */
	mrs	x1, CurrentEL
	lsr	x1, x1, #2
	cmp	x1, #2
	b.ne	_sec_in_el1

	mov	x1, #(1 << 31)
	msr	hcr_el2, x1
	msr	sctlr_el1, xzr
	mov	x1, #0x3c5
	msr	spsr_el2, x1
	adr	x1, _sec_in_el1
	msr	elr_el2, x1
	isb
	eret

_sec_in_el1:
	msr	daifset, #0xf
	msr	spsel, #1
	adr	x1, _sec_stacks
	add	x1, x1, x0, lsl #12
	add	x1, x1, #0x1000
	mov	sp, x1
	adr	x1, vectors
	msr	vbar_el1, x1
	isb
	bl	secondary_main
4:	wfe
	b	4b

/*
 * Exception vectors. Each slot stashes x29/x30, loads its slot number
 * and jumps to the common path, which saves x0-x28 and calls
 * exc_handler(slot, regs).
 */
	.balign	2048
vectors:
	.set	slot, 0
	.rept	16
	.balign	128
	sub	sp, sp, #16
	stp	x29, x30, [sp]
	mov	x0, #slot
	b	common_vector
	.set	slot, slot + 1
	.endr

common_vector:
	sub	sp, sp, #240
	stp	x0,  x1,  [sp, #0]
	stp	x2,  x3,  [sp, #16]
	stp	x4,  x5,  [sp, #32]
	stp	x6,  x7,  [sp, #48]
	stp	x8,  x9,  [sp, #64]
	stp	x10, x11, [sp, #80]
	stp	x12, x13, [sp, #96]
	stp	x14, x15, [sp, #112]
	stp	x16, x17, [sp, #128]
	stp	x18, x19, [sp, #144]
	stp	x20, x21, [sp, #160]
	stp	x22, x23, [sp, #176]
	stp	x24, x25, [sp, #192]
	stp	x26, x27, [sp, #208]
	stp	x28, xzr, [sp, #224]
	mov	x1, sp
	bl	exc_handler
5:	wfe
	b	5b
