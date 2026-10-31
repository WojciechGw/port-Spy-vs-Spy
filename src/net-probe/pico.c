#include <rp6502.h>
#include <fcntl.h>
#include <errno.h>
#include <stdlib.h>
#include "platform.h"

/* RP6502's runtime opts into argv storage through this allocator hook. */
void *__fastcall__ __argv_mem(size_t size) { return malloc(size); }

static int modem = -1;
static unsigned enabled;
static unsigned char previous, colour;
unsigned long probe_draws, probe_missed;

unsigned long probe_ms(void) { return (unsigned long)ria_attr_get(RIA_ATTR_CLK_RUN_MS); }
int probe_open(void) { modem = open("AT:", O_RDWR); return modem; }
int probe_read(void *p, unsigned n) { return read_xstack(p, n, modem); }
int probe_write(const void *p, unsigned n) { return write_xstack(p, n, modem); }
void probe_close(void) { if (modem >= 0) { close(modem); modem = -1; } }
int probe_abort(void) { return (xram0_peek8(0xa005) & 2) != 0; }

int probe_init(unsigned load)
{
    /* 64x64 8bpp overlay, default palette. Synthetic 4 KiB/frame workload.
       Explicit bytes avoid compiler packing and word-size assumptions. */
    static const unsigned char config[14] = {
        0, 0, 0, 0, 0, 0, 64, 0, 64, 0, 0, 0x80, 0xff, 0xff
    };
    enabled = load;
    /* A missing monotonic clock must fail before entering a timed wait. */
    if (ria_attr_get(RIA_ATTR_CLK_RUN_MS) < 0) return -1;
    xram0_set(0xa000, 0, 32);
    if (xreg(0, 0, 0, 0xa000) < 0) return -1;
    if (load) {
        if (xreg(1, 0, 0, 1) < 0) return -1;
        xram0_set(0x8000, 0, 4096);
        xram0_write(0x9000, config, sizeof(config));
        if (xreg(1, 0, 1, 3, 3, 0x9000, 2) < 0) return -1;
    }
    previous = RIA.vsync;
    return 0;
}

void probe_poll(void)
{
    unsigned char current, elapsed;
    if (!enabled) return;
    current = RIA.vsync;
    elapsed = current - previous;
    if (!elapsed) return;
    previous = current;
    probe_missed += elapsed - 1;
    ++colour;
    xram0_set(0x8000, colour, 4096);
    ++probe_draws;
}

void probe_finish(void)
{
    xreg(0, 0, 0, 0xffff);
    if (enabled) xreg(1, 0, 0, 0);
}
