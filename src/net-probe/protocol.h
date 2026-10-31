#ifndef PROBE_PROTOCOL_H
#define PROBE_PROTOCOL_H
#define FRAME_SIZE 32
void frame_make(unsigned char *p, unsigned char type, unsigned seq, unsigned long stamp);
void frame_reply(unsigned char *p, unsigned char type);
int frame_valid(const unsigned char *p);
unsigned frame_seq(const unsigned char *p);
unsigned long frame_stamp(const unsigned char *p);
unsigned frame_crc(const unsigned char *p, unsigned count);
#endif
