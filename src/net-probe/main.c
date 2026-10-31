/* Standalone AT:/raw TCP latency probe. Never linked into the game. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include "platform.h"
#include "protocol.h"

#define SAMPLES 300
#define TIMEOUT 5000UL
static unsigned chunk = 32, count = SAMPLES;
static unsigned char tx[FRAME_SIZE], rx[FRAME_SIZE], input[64];
static unsigned in_pos, in_end, used;
static unsigned samples[SAMPLES], completed;
static unsigned phase_tx[SAMPLES], phase_rx[SAMPLES];
static unsigned long sample_start[SAMPLES];
static unsigned long send_begin_ms, send_end_ms, frame_first_ms;
static unsigned attempted;
static unsigned long reads, writes, empty_reads, empty_writes, short_reads, short_writes;
static unsigned long read_max, write_max, poll_max, last_poll, discarded;
static char line[96], command[100];
static const char *failure;
static int io_errno;
static const char *stage = "SETUP";
static unsigned long stage_start;

static void set_stage(const char *name)
{
    stage = name;
    stage_start = probe_ms();
}

static int service(void)
{
    unsigned long now = probe_ms(), gap = now - last_poll;
    if (gap > poll_max) poll_max = gap;
    last_poll = now;
    if (probe_abort()) { failure = "CANCELLED (Escape)"; return 0; }
    probe_poll();
    return 1;
}

static int read_some(void *p, unsigned n)
{
    int got, saved;
    unsigned long start = probe_ms(), elapsed;
    got = probe_read(p, n); saved = errno;
    elapsed = probe_ms() - start;
    ++reads;
    if (elapsed > read_max) read_max = elapsed;
    if (got < 0 && saved == EAGAIN) got = 0;
    if (got < 0 || got > n) { io_errno = saved; failure = "READ ERROR"; return -1; }
    if (!got) ++empty_reads;
    else if (got < n) ++short_reads;
    return got;
}

static int send_bytes(const unsigned char *p, unsigned n)
{
    unsigned part;
    int sent, saved;
    unsigned long start = probe_ms(), call, elapsed;
    send_begin_ms = start;
    while (n) {
        if (!service()) return 0;
        if (probe_ms() - start >= TIMEOUT) { failure = "WRITE TIMEOUT"; return 0; }
        part = n < chunk ? n : chunk;
        call = probe_ms(); sent = probe_write(p, part); saved = errno;
        elapsed = probe_ms() - call;
        ++writes;
        if (elapsed > write_max) write_max = elapsed;
        if (sent < 0 && saved == EAGAIN) sent = 0;
        if (sent < 0 || sent > part) { io_errno = saved; failure = "WRITE ERROR"; return 0; }
        if (!sent) ++empty_writes;
        else {
            if (sent < part) ++short_writes;
            p += sent; n -= sent;
        }
    }
    send_end_ms = probe_ms();
    return 1;
}

/* Read a block, but parse through the final LF before sending another command.
   Firmware can reject writes while the tail of an AT response is unread.
   Retain bytes following CONNECT for receive_frame(), including binary data. */
static int response(const char *wanted, unsigned long timeout)
{
    unsigned pos = 0;
    unsigned char ch;
    int got;
    unsigned long start = probe_ms();
    while (probe_ms() - start < timeout) {
        if (!service()) return 0;
        if (in_pos == in_end) {
            got = read_some(input, sizeof(input));
            if (got < 0) return 0;
            in_pos = 0; in_end = got;
            if (!got) continue;
        }
        ch = input[in_pos++];
        if (ch == '\r') continue;
        if (ch == '\n') {
            if (!pos) continue;
            line[pos] = 0; pos = 0;
            if (!strncmp(line, wanted, strlen(wanted)) &&
                (!line[strlen(wanted)] || line[strlen(wanted)] == ' ')) return 1;
            if (!strcmp(line, "ERROR") || !strcmp(line, "NO CARRIER") ||
                !strcmp(line, "BUSY") || !strcmp(line, "NO ANSWER")) {
                failure = line; return 0;
            }
        } else if (pos < sizeof(line)-1) line[pos++] = ch;
        else { failure = "AT RESPONSE TOO LONG"; return 0; }
    }
    failure = "AT RESPONSE TIMEOUT";
    return 0;
}

static int at(const char *s)
{
    return send_bytes((const unsigned char *)s, strlen(s)) && response("OK", 5000);
}

static int receive_frame(void)
{
    unsigned char ch;
    int got;
    unsigned long start = probe_ms();
    while (probe_ms()-start < TIMEOUT) {
        if (!service()) return 0;
        if (in_pos == in_end) {
            got = read_some(input, chunk);
            if (got < 0) return 0;
            in_pos = 0; in_end = got;
            if (!got) continue;
        }
        ch = input[in_pos++];
        if (!used && ch != 0xa5) {
            /* Ignore CONNECT's LF and any modem status text. A missing peer
               is reported by the bounded frame timeout, never by read()==0. */
            ++discarded;
            continue;
        }
        if (!used) frame_first_ms = probe_ms();
        rx[used++] = ch;
        if (used == FRAME_SIZE) {
            used = 0;
            if (!frame_valid(rx)) { failure = "FRAME CRC/HEADER ERROR"; return 0; }
            return 1;
        }
    }
    failure = "FRAME TIMEOUT (peer silent/disconnected)";
    return 0;
}

static int exchange(unsigned char type, unsigned seq, unsigned long start)
{
    unsigned long received_at;
    frame_make(tx, type, seq, start);
    if (!send_bytes(tx, FRAME_SIZE) || !receive_frame()) return 0;
    received_at = probe_ms();
    if (type == 'P') {
        phase_tx[seq] = (unsigned)(send_end_ms-send_begin_ms);
        phase_rx[seq] = (unsigned)(received_at-send_end_ms);
    }
    frame_reply(tx, type == 'P' ? 'R' : 'A');
    if (memcmp(tx, rx, FRAME_SIZE)) { failure = "REPLY SEQUENCE/PAYLOAD ERROR"; return 0; }
    return 1;
}

static int client(void)
{
    unsigned seq;
    unsigned long start, elapsed, origin = 0;
    for (seq = 0; seq < count; ++seq) {
        start = probe_ms();
        if (!seq) origin = start;
        sample_start[completed] = start-origin;
        attempted = seq+1;
        if (!exchange('P', seq, start)) return 0;
        elapsed = probe_ms()-start;
        if (elapsed > 65535UL) { failure = "RTT OVERFLOW"; return 0; }
        samples[completed++] = (unsigned)elapsed;
        /* Nominal 60 Hz workload, without sending a catch-up burst. */
        while (probe_ms()-start < 17) if (!service()) return 0;
    }
    return exchange('Q', count, probe_ms());
}

static int server(void)
{
    unsigned expected = 0;
    unsigned char type;
    unsigned long start, received_at, span, origin = 0;
    for (;;) {
        if (!receive_frame()) return 0;
        received_at = probe_ms();
        type = rx[4];
        frame_make(tx, type, expected, frame_stamp(rx));
        if ((type != 'P' && type != 'Q') || memcmp(tx, rx, FRAME_SIZE)) {
            failure = "REQUEST SEQUENCE/PAYLOAD ERROR"; return 0;
        }
        if (type == 'P') {
            if (expected >= SAMPLES) { failure = "SAMPLE LIMIT"; return 0; }
            if (!expected) origin = frame_first_ms;
            sample_start[expected] = frame_first_ms-origin;
            attempted = expected+1;
        }
        frame_reply(tx, type == 'P' ? 'R' : 'A');
        if (!send_bytes(tx, FRAME_SIZE)) return 0;
        if (type == 'Q') {
            /* Give the firmware's TX queue time to drain before closing. */
            start = probe_ms();
            while (probe_ms()-start < 1000) if (!service()) return 0;
            return 1;
        }
        span = send_end_ms-frame_first_ms;
        if (span > 65535UL) { failure = "SPAN OVERFLOW"; return 0; }
        samples[expected] = (unsigned)span;
        phase_rx[expected] = (unsigned)(received_at-frame_first_ms);
        phase_tx[expected] = (unsigned)(send_end_ms-send_begin_ms);
        ++expected; ++completed;
    }
}

static int number(const char *s, unsigned low, unsigned high, unsigned *out)
{
    unsigned long v = 0;
    if (!*s) return 0;
    while (*s) {
        if (*s < '0' || *s > '9') return 0;
        v = v*10 + (*s++ - '0');
        if (v > high) return 0;
    }
    if (v < low) return 0;
    *out = (unsigned)v; return 1;
}

static int destination(const char *s)
{
    const char *colon;
    unsigned n;
    if (!*s || strlen(s) > 80) return 0;
    colon = strchr(s, ':');
    if (!colon || colon == s || !number(colon+1, 1, 65535U, &n)) return 0;
    while (s < colon) {
        if (!((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z') ||
              (*s >= '0' && *s <= '9') || *s == '.' || *s == '-')) return 0;
        ++s;
    }
    return 1;
}

/* Called only after closing the modem. Keep acquisition order intact so that
   the slowest RTTs retain their sample numbers and start times. Ties keep the
   earlier sample first. No sorting, counters or printing in the timed loop. */
void probe_rtt_report(const unsigned *values, const unsigned long *started, unsigned n)
{
    static unsigned order[SAMPLES];
    unsigned i, j, index, over200 = 0, over500 = 0, over1000 = 0;
    unsigned long sum = 0;
    if (!n) return;
    for (i = 0; i < n; ++i) {
        sum += values[i];
        if (values[i] > 200) ++over200;
        if (values[i] > 500) ++over500;
        if (values[i] > 1000) ++over1000;
        /* Descending, stable order also makes top-five output deterministic. */
        j = i;
        while (j && values[order[j-1]] < values[i]) { order[j] = order[j-1]; --j; }
        order[j] = i;
    }
    printf("RTT ms: min=%u avg=%lu p50=%u p95=%u max=%u\n", values[order[n-1]], sum/n,
           values[order[n-1-(n-1)/2]], values[order[n-(n*95U+99)/100]], values[order[0]]);
    printf("RTT counts: >200ms=%u >500ms=%u >1000ms=%u\n", over200, over500, over1000);
    printf("First: #1 at=%lu ms rtt=%u ms\n", started[0], values[0]);
    puts("Slowest (1-based sample; at=start since first sample):");
    for (i = 0; i < n && i < 5; ++i) {
        index = order[i];
        printf("#%u at=%lu ms rtt=%u ms\n", index+1, started[index], values[index]);
    }
}

/* Same 1-based sequence numbers on both machines; all durations are LOCAL.
   DIAL: tx + wait + other = RTT. LISTEN: rx + prep + tx = local span.
   rx begins when the first frame byte is consumed, not while idle between
   requests; it includes any wait for remaining bytes and CRC validation. */
static void phase_report(int dial)
{
    unsigned i, j, k, pick, chosen[5], max_tx = 0, max_rx = 0, max_other = 0;
    unsigned other, best;
    int seen;
    if (!completed) return;
    for (i = 0; i < completed; ++i) {
        if (phase_tx[i] > phase_tx[max_tx]) max_tx = i;
        if (phase_rx[i] > phase_rx[max_rx]) max_rx = i;
        other = samples[i]-phase_tx[i]-phase_rx[i];
        if (other > samples[max_other]-phase_tx[max_other]-phase_rx[max_other]) max_other = i;
    }
    printf("%s phases ms (local clock only):\n", dial ? "DIAL" : "LISTEN");
    printf("Max tx=%u(#%u) %s=%u(#%u)\n", phase_tx[max_tx], max_tx+1,
           dial ? "wait" : "rx", phase_rx[max_rx], max_rx+1);
    printf("Max %s=%u(#%u)\n", dial ? "other" : "prep",
           samples[max_other]-phase_tx[max_other]-phase_rx[max_other], max_other+1);
    puts(dial ? "Phases of slowest RTT samples:" : "Slowest LISTEN spans (first byte to TX accepted):");
    for (j = 0; j < 5 && j < completed; ++j) {
        pick = 0; best = 0;
        for (i = 0; i < completed; ++i) {
            seen = 0;
            for (k = 0; k < j; ++k) if (chosen[k] == i) seen = 1;
            if (!seen && (!best || samples[i] > samples[pick])) { pick = i; best = 1; }
        }
        chosen[j] = pick;
        printf("#%u span=%u tx=%u %s=%u %s=%u\n", pick+1, samples[pick], phase_tx[pick],
               dial ? "wait" : "rx", phase_rx[pick], dial ? "other" : "prep",
               samples[pick]-phase_tx[pick]-phase_rx[pick]);
    }
}

static void summary(int dial, int ok)
{
    printf("\n%s: %s; samples=%u\n", dial ? "DIAL" : "LISTEN", ok ? "PASS" : failure, completed);
    if (!ok) printf("Stage=%s elapsed=%lu ms\n", stage, probe_ms()-stage_start);
    if (io_errno) printf("I/O errno=%d\n", io_errno);
    if (!dial && attempted > completed)
        printf("Incomplete reply #%u (excluded from LISTEN phases)\n", attempted);
    if (dial) {
        if (attempted > completed)
            printf("Incomplete sample #%u at=%lu ms (excluded from RTT stats)\n", attempted, sample_start[completed]);
        probe_rtt_report(samples, sample_start, completed);
    }
    phase_report(dial);
    printf("IO calls read=%lu write=%lu; empty=%lu/%lu short=%lu/%lu\n", reads, writes,
           empty_reads, empty_writes, short_reads, short_writes);
    printf("Max ms: read=%lu write=%lu poll-gap=%lu\n", read_max, write_max, poll_max);
    printf("Graphics draws=%lu missed=%lu; discarded=%lu\n", probe_draws, probe_missed, discarded);
}

int main(int argc, char **argv)
{
    static char role[12], endpoint[84], load_text[8];
    unsigned load = 0, port;
    int dial, ok = 0;
    const char *mode, *target;
    puts("SPY NETWORK PROBE 4 - standalone AT:/TCP test");
    if (argc == 1) {
        printf("Role (listen/dial): "); if (!fgets(role, sizeof(role), stdin)) return 2;
        role[strcspn(role, "\r\n")] = 0;
        printf("Port (listen) or IPv4:port (dial): "); if (!fgets(endpoint, sizeof(endpoint), stdin)) return 2;
        endpoint[strcspn(endpoint, "\r\n")] = 0;
        printf("Graphics load (0/1): "); if (!fgets(load_text, sizeof(load_text), stdin)) return 2;
        load_text[strcspn(load_text, "\r\n")] = 0;
        if (!number(load_text, 0, 1, &load)) return 2;
        mode = role; target = endpoint;
    } else {
        if (argc < 3 || argc > 6) goto usage;
        mode = argv[1]; target = argv[2];
        if (argc > 3 && !number(argv[3], 0, 1, &load)) goto usage;
        if (argc > 4 && !number(argv[4], 1, 64, &chunk)) goto usage;
        if (argc > 5 && !number(argv[5], 1, SAMPLES, &count)) goto usage;
    }
    dial = !strcmp(mode, "dial");
    if ((!dial && strcmp(mode, "listen")) || (dial ? !destination(target) : !number(target, 1, 65535U, &port))) goto usage;
    printf("Role=%s target=%s load=%u chunk=%u samples=%u\n", mode, target, load, chunk, count);
    puts("Escape cancels. Configuring modem (5 s/command).");
    if (probe_init(load) < 0) { puts("Clock/graphics setup failed"); probe_finish(); return 1; }
    last_poll = probe_ms();
    if (probe_open() < 0) { printf("Cannot open AT: errno=%d (requires RIA-W modem firmware)\n", errno); probe_finish(); return 1; }
    set_stage("AT CONFIG");
    if (!at("ATE0Q0V1X0\\N0S2=128\r")) goto done;
    if (dial) {
        set_stage("AT DIAL");
        sprintf(command, "ATD%s\r", target);
        if (!send_bytes((unsigned char *)command, strlen(command))) goto done;
    } else {
        set_stage("AT AUTO ANSWER");
        if (!at("ATS0=1\r")) goto done;
        set_stage("AT LISTEN PORT");
        sprintf(command, "AT\\L%s\r", target);
        if (!at(command)) goto done;
    }
    puts("Modem ready. Waiting for connection (120 s).");
    set_stage("CONNECT");
    if (!response("CONNECT", 120000UL)) goto done;
    puts("Connected; measuring. No per-packet printing.");
    reads = writes = empty_reads = empty_writes = short_reads = short_writes = 0;
    read_max = write_max = poll_max = probe_draws = probe_missed = 0;
    last_poll = probe_ms();
    set_stage("MEASURE");
    ok = dial ? client() : server();
done:
    probe_close(); probe_finish(); summary(dial, ok);
    return ok ? 0 : 1;
usage:
    puts("Usage: net-probe listen PORT [load 0/1] [chunk 1..64] [samples 1..300]");
    puts("       net-probe dial IPv4:PORT [load 0/1] [chunk 1..64] [samples 1..300]");
    return 2;
}
