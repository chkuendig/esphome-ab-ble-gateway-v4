#include "protocol.h"
#include <string.h>

static const uint8_t prefix[] = "OK+SCAN:";
static void discard(xbg_parser *p, size_t n) {
    memmove(p->buf, p->buf + n, p->used - n);
    p->used -= n;
}
xbg_event xbg_feed(xbg_parser *p, uint8_t byte, xbg_ad *ad,
                   char *line, size_t line_cap) {
    if (p->used == sizeof(p->buf)) { discard(p, 1); p->malformed++; }
    p->buf[p->used++] = byte;
    /* Find a complete prefix after noise, while preserving partial prefixes. */
    if (p->used < 8 || memcmp(p->buf, prefix, 8))
        for (size_t i = 1; i + 8 <= p->used; ++i) {
            if (!memcmp(p->buf + i, prefix, 8)) { discard(p, i); break; }
        }
    if (p->used >= 8 && !memcmp(p->buf, prefix, 8)) {
        if (p->used < 17) return XBG_NONE;
        size_t n = p->buf[16];
        if (n > XBG_MAX_AD || p->buf[15] > 4) {
            discard(p, 1); p->malformed++; return XBG_NONE;
        }
        if (p->used < n + 19) return XBG_NONE;
        if (p->buf[n + 17] != '\r' || p->buf[n + 18] != '\n') {
            discard(p, 1); p->malformed++; return XBG_NONE;
        }
        ad->data[0] = p->buf[15];
        memcpy(ad->data + 1, p->buf + 8, 6);
        ad->data[7] = p->buf[14];
        memcpy(ad->data + 8, p->buf + 17, n);
        ad->len = n + 8;
        discard(p, n + 19);
        return XBG_AD;
    }
    if (p->used >= 2 && p->buf[p->used - 2] == '\r' && byte == '\n') {
        size_t n = p->used - 2;
        if (line_cap) {
            if (n >= line_cap) n = line_cap - 1;
            for (size_t i = 0; i < n; ++i)
                line[i] = p->buf[i] >= 32 && p->buf[i] < 127 ? p->buf[i] : '.';
            line[n] = 0;
        }
        p->used = 0;
        return XBG_LINE;
    }
    return XBG_NONE;
}
