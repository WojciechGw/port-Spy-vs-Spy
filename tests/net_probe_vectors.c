/* Independent interoperability reference: compile the Pico's real framing. */
#include <stdio.h>
#include "protocol.h"

int main(void)
{
    unsigned char frame[32];
    unsigned i, j;
    static const unsigned char types[] = {'P', 'P', 'Q', 'R', 'A'};
    static const unsigned seqs[] = {0, 299, 300, 255, 300};
    static const unsigned long stamps[] = {0, 0xffffffffUL, 0x12345678UL, 65536UL, 42};
    for (i = 0; i < 5; ++i) {
        frame_make(frame, types[i], seqs[i], stamps[i]);
        for (j = 0; j < 32; ++j) printf("%02x", frame[j]);
        putchar('\n');
    }
    return 0;
}
