/* Firmware boundary simulator; the application and framing code are real.
   This deliberately splits all transfers and injects temporary backpressure. */
#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "platform.h"
#include "protocol.h"

static unsigned mode, server_side, received, incoming, outgoing, rcalls, wcalls;
static unsigned char queue[512], packet[32], part[32];
static char cmd[128];
static unsigned pos, packet_pos;
static unsigned control_end;
static int connected;
static int pending_connect;
static unsigned long ticks, began;
static unsigned long withheld_until;
#ifndef PROBE_NATIVE
static int delay_injected;
unsigned long probe_draws, probe_missed;
#endif
extern int probe_main(int argc, char **argv);
extern void probe_rtt_report(const unsigned *values, const unsigned long *started, unsigned n);

static void append(const void *p, unsigned n)
{
    assert(incoming+n < sizeof(queue));
    memcpy(queue+incoming, p, n); incoming += n;
}
static void message(const char *s) { append(s, strlen(s)); control_end = incoming; }
static void request(unsigned seq)
{
    frame_make(packet, seq < (mode == 27 ? 301 : 3) ? 'P' : 'Q', mode == 14 ? seq+1 : seq, 77UL);
    append(packet, 32);
}

int probe_open(void) { return mode == 1 ? -1 : 3; }
void probe_close(void) { }
#ifndef PROBE_NATIVE
unsigned long probe_ms(void) { ticks += pending_connect ? 100UL : 1UL; return ticks; }
void probe_finish(void) { }
int probe_abort(void) { return mode == 9 && connected && ticks-began > 30; }
void probe_poll(void) { if (ticks % 17 == 0) ++probe_draws; }

int probe_init(unsigned load)
{
    unsigned i;
    (void)load;
    assert(frame_crc((const unsigned char *)"123456789", 9) == 0x29b1);
    frame_make(packet, 'P', 65535U, 0xfffffff0UL);
    assert(frame_valid(packet) && frame_seq(packet) == 65535U && frame_stamp(packet) == 0xfffffff0UL);
    for (i = 0; i < 32; ++i) {
        packet[i] ^= 1; assert(!frame_valid(packet)); packet[i] ^= 1;
    }
    if (mode == 10) ticks = 0xfffffff0UL;
    return 0;
}
#endif

int probe_read(void *p, unsigned n)
{
    unsigned got;
#ifdef PROBE_NATIVE
    ticks = probe_ms();
#endif
    ++rcalls;
    if (withheld_until && ticks < withheld_until) return 0;
    if (pending_connect && mode == 16 && ticks-began >= 60000UL) {
        pending_connect = 0;
        message("\r\nCONNECT\r\n");
        if (server_side) request(0);
    }
    if (mode == 6 && connected) { errno = EIO; return -1; }
    if (rcalls % 11 == 0) { errno = EAGAIN; return -1; }
    if (rcalls % 4 == 0) return 0;
    got = incoming-outgoing;
    if (got > n) got = n;
    if (got > 7) got = 7;
    memcpy(p, queue+outgoing, got); outgoing += got;
#ifndef PROBE_NATIVE
    if (mode == 26 && server_side && received == 2 && got && !delay_injected) {
        withheld_until = ticks+1200; delay_injected = 1;
    }
#endif
    if (outgoing >= control_end) control_end = 0;
    if (outgoing == incoming) outgoing = incoming = 0;
    return got;
}

int probe_write(const void *p, unsigned n)
{
    unsigned i, taken;
    unsigned char ch;
#ifdef PROBE_NATIVE
    ticks = probe_ms();
#endif
    ++wcalls;
    /* Firmware holds writes until its generated AT response is consumed. */
    if (control_end) return 0;
#ifndef PROBE_NATIVE
    if (mode == 25 && server_side && received == 2 && !delay_injected) {
        ticks += 1200; delay_injected = 1;
    }
#endif
    if (mode == 5 && connected) return 0;
    if (wcalls % 13 == 0) { errno = EAGAIN; return -1; }
    if (wcalls % 5 == 0) return 0;
    taken = n > 3 ? 3 : n;
    for (i = 0; i < taken; ++i) {
        ch = ((const unsigned char *)p)[i];
        if (!connected) {
            if (ch != '\r') { assert(pos < sizeof(cmd)-1); cmd[pos++] = ch; continue; }
            cmd[pos] = 0; pos = 0;
            if (mode == 7) { message("\r\nERROR\r\n"); continue; }
            /* ad6293c accepts AT\L6502; its numeric parser rejects '='. */
            if (!strncmp(cmd, "AT\\L=", 5)) { message("\r\nERROR\r\n"); continue; }
            if (!strncmp(cmd, "ATD", 3) || !strncmp(cmd, "AT\\L", 4)) {
                server_side = cmd[2] == '\\';
                if (server_side) message("\r\nOK\r\nRING\r\n");
                connected = 1; began = ticks;
                if (mode == 16 || mode == 17) pending_connect = 1;
                else {
                    message("\r\nCONNECT\r\n");
                    if (server_side) request(0);
                }
            } else message("\r\nOK\r\n");
        } else {
            part[packet_pos++] = ch;
            if (packet_pos != 32) continue;
            packet_pos = 0; assert(frame_valid(part));
            if (server_side) {
                assert(frame_seq(part) == received);
                assert(part[4] == (received < (mode == 27 ? 301 : 3) ? 'R' : 'A'));
                if (received < (mode == 27 ? 301 : 3)) request(++received);
            } else {
                assert(frame_seq(part) == received++);
#ifndef PROBE_NATIVE
                if ((mode == 21 && received == 1) || (mode == 22 && received == 3)) ticks += 1200;
                if (mode == 24 && received == 3) withheld_until = ticks+1200;
#endif
                memcpy(packet, part, 32);
                frame_reply(packet, part[4] == 'P' ? 'R' : 'A');
                if (mode == 2) packet[31] ^= 1;
                if (mode == 3) { packet[6]++; frame_reply(packet, 'R'); }
                if (mode == 13) { packet[20] ^= 1; frame_reply(packet, 'R'); }
                if (mode == 4 || (mode == 23 && received == 3)) message("\r\nNO CARRIER\r\n");
                else append(packet, mode == 12 ? 10 : 32);
            }
        }
    }
    return taken;
}

int main(int argc, char **argv)
{
    int result;
    unsigned i;
    static unsigned values[300];
    static unsigned long starts[300];
    static const unsigned fixture[] = {200, 201, 500, 501, 1000, 1001, 1001, 50, 1390};
    static const unsigned long times[] = {0, 200, 401, 901, 1402, 2402, 3403, 4404, 4454};
    assert(argc > 1);
    mode = atoi(argv[1]);
    if (mode == 18) { probe_rtt_report(fixture, times, 9); return 0; }
    if (mode == 19) {
        probe_rtt_report(values, starts, 0);
        puts("EMPTY DONE");
        probe_rtt_report(values, starts, 1);
        return 0;
    }
    if (mode == 20) {
        for (i = 0; i < 300; ++i) { values[i] = i+1; starts[i] = (unsigned long)i*100; }
        probe_rtt_report(values, starts, 300);
        assert(values[0] == 1 && values[299] == 300 && starts[299] == 29900UL);
        return 0;
    }
    result = probe_main(argc-1, argv+1);
    if (mode == 16) assert(result == 0 && ticks-began >= 60000UL);
    if (mode == 17) assert(result == 1 && ticks-began >= 120000UL && ticks-began < 123000UL);
    return result;
}
