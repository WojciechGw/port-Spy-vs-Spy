#ifndef PROBE_PLATFORM_H
#define PROBE_PLATFORM_H
unsigned long probe_ms(void);
int probe_open(void);
int probe_read(void *buf, unsigned count);
int probe_write(const void *buf, unsigned count);
void probe_close(void);
int probe_init(unsigned load);
void probe_poll(void);
int probe_abort(void);
void probe_finish(void);
extern unsigned long probe_draws, probe_missed;
#endif
