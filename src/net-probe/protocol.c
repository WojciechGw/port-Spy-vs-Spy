#include "protocol.h"

unsigned frame_crc(const unsigned char *p, unsigned count)
{
    unsigned crc = 0xffff;
    unsigned char bit;
    while (count--) {
        crc ^= (unsigned)*p++ << 8;
        for (bit = 0; bit < 8; ++bit)
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1;
    }
    return crc;
}

unsigned frame_seq(const unsigned char *p) { return p[6] | (unsigned)p[7] << 8; }
unsigned long frame_stamp(const unsigned char *p)
{
    return p[8] | (unsigned long)p[9] << 8 | (unsigned long)p[10] << 16 | (unsigned long)p[11] << 24;
}

void frame_reply(unsigned char *p, unsigned char type)
{
    unsigned crc;
    p[4] = type;
    crc = frame_crc(p, 30);
    p[30] = crc;
    p[31] = crc >> 8;
}

void frame_make(unsigned char *p, unsigned char type, unsigned seq, unsigned long stamp)
{
    unsigned char i;
    p[0] = 0xa5; p[1] = 0x5a; p[2] = 'N'; p[3] = 1;
    p[5] = FRAME_SIZE;
    p[6] = seq; p[7] = seq >> 8;
    for (i = 8; i < 12; ++i) { p[i] = stamp; stamp >>= 8; }
    for (i = 12; i < 30; ++i) p[i] = (unsigned char)(seq + i * 17);
    /* Exercise raw TCP, including bytes special to telnet and Hayes escape. */
    p[12] = 0; p[13] = 255; p[14] = p[15] = p[16] = '+';
    p[17] = '\r'; p[18] = '\n';
    frame_reply(p, type);
}

int frame_valid(const unsigned char *p)
{
    return p[0] == 0xa5 && p[1] == 0x5a && p[2] == 'N' && p[3] == 1 &&
           p[5] == FRAME_SIZE && frame_crc(p, 30) == (p[30] | (unsigned)p[31] << 8);
}
