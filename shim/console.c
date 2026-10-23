/*
 * Minimal text console on the bootloader splash framebuffer and early UART.
 * With the MMU off every access is Device memory, so stay aligned (-mstrict-align).
 */
#include "console.h"
#include "font.h"

#ifndef CON_SCALE
#define SCALE		3
#else
#define SCALE		CON_SCALE
#endif

#define CH_W		(8 * SCALE)
#define CH_H		(16 * SCALE)
#define MARGIN		24
#define LABEL_COLS	8

volatile uint32_t *con_fb = (volatile uint32_t *)FB_BASE;
static uint32_t con_bg;
static int row;

void uart_putc(char c)
{
#ifdef UART_BASE
	/* 8250 / MediaTek UART: wait until Transmit Holding Register Empty */
	while (!(*(volatile uint32_t *)UART_LSR & UART_LSR_THRE))
		;
	*(volatile uint32_t *)UART_THR = (uint32_t)(uint8_t)c;
	if (c == '\n') {
		while (!(*(volatile uint32_t *)UART_LSR & UART_LSR_THRE))
			;
		*(volatile uint32_t *)UART_THR = (uint32_t)'\r';
	}
#else
	(void)c;
#endif
}

void uart_puts(const char *s)
{
	while (*s)
		uart_putc(*s++);
}

void con_clear(uint32_t bg)
{
	for (int y = 0; y < FB_H; y++) {
		volatile uint32_t *line = con_fb + y * (FB_STRIDE / 4);
		for (int x = 0; x < FB_W; x++)
			line[x] = bg;
	}
	con_bg = bg;
	row = 0;
	uart_puts("\n[CON CLEAR]\n");
}

static void put_char(int col, char ch, uint32_t fg)
{
	if (ch < 0x20 || ch > 0x7e)
		ch = '?';
	const unsigned char *g = font8x16[ch - 0x20];
	int x0 = MARGIN + col * CH_W, y0 = MARGIN + row * CH_H;
	if (x0 + CH_W > FB_W || y0 + CH_H > FB_H)
		return;
	for (int gy = 0; gy < 16; gy++)
		for (int gx = 0; gx < 8; gx++) {
			uint32_t c = (g[gy] & (0x80 >> gx)) ? fg : con_bg;
			for (int sy = 0; sy < SCALE; sy++) {
				volatile uint32_t *p = con_fb + (y0 + gy * SCALE + sy) * (FB_STRIDE / 4)
						       + x0 + gx * SCALE;
				for (int sx = 0; sx < SCALE; sx++)
					p[sx] = c;
			}
		}
}

static int put_str(int col, const char *s, uint32_t fg)
{
	while (*s)
		put_char(col++, *s++, fg);
	return col;
}

static void fmt_hex(char *buf, uint64_t v, int digits)
{
	static const char hex[] = "0123456789ABCDEF";
	for (int i = 0; i < digits; i++)
		buf[i] = hex[(v >> (4 * (digits - 1 - i))) & 0xf];
	buf[digits] = 0;
}

void con_skip(void)
{
	row++;
	uart_putc('\n');
}

void con_str(const char *label, const char *s)
{
	put_str(0, label, YELLOW);
	put_str(LABEL_COLS, s, WHITE);
	row++;

	uart_puts(label);
	uart_puts(": ");
	uart_puts(s);
	uart_putc('\n');
}

void con_hex(const char *label, uint64_t v)
{
	char buf[17];
	fmt_hex(buf, v, 16);
	con_str(label, buf);
}

void con_hex2(const char *label, const char *a, uint32_t va, const char *b, uint32_t vb)
{
	char buf[9];
	int col = put_str(0, label, YELLOW);
	col = col < LABEL_COLS ? LABEL_COLS : col + 1;
	col = put_str(col, a, YELLOW);
	fmt_hex(buf, va, 8);
	col = put_str(col, buf, WHITE);

	uart_puts(label);
	uart_puts(" ");
	uart_puts(a);
	uart_puts(buf);

	if (b) {
		col = put_str(col + 1, b, YELLOW);
		fmt_hex(buf, vb, 8);
		put_str(col, buf, WHITE);

		uart_puts(" ");
		uart_puts(b);
		uart_puts(buf);
	}
	row++;
	uart_putc('\n');
}
