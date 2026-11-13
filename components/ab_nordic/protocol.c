#include "protocol.h"
#include <string.h>

void xbg_capture_append(xbg_capture *capture, const uint8_t *bytes, size_t length) {
    static const char digits[] = "0123456789abcdef";
    size_t used = capture->total < XBG_CAPTURE_BYTES ? capture->total : XBG_CAPTURE_BYTES;
    size_t count = length < XBG_CAPTURE_BYTES - used ? length : XBG_CAPTURE_BYTES - used;
    for (size_t i = 0; i < count; ++i) {
        capture->hex[2 * (used + i)] = digits[bytes[i] >> 4];
        capture->hex[2 * (used + i) + 1] = digits[bytes[i] & 15];
    }
    capture->hex[2 * (used + count)] = 0;
    capture->total = length > SIZE_MAX - capture->total ? SIZE_MAX : capture->total + length;
}

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

typedef struct { uint8_t *p; size_t n, cap; bool failed; } writer;
static void raw(writer *w, const void *p, size_t n) {
    if (w->failed || n > w->cap - w->n) { w->failed = true; return; }
    memcpy(w->p + w->n, p, n); w->n += n;
}
static void byte(writer *w, uint8_t b) { raw(w, &b, 1); }
static void str(writer *w, const char *s) {
    size_t n = strlen(s); byte(w, 0xa0 | n); raw(w, s, n);
}
static void u32(writer *w, uint32_t n) {
    byte(w, 0xce);
    for (int i = 24; i >= 0; i -= 8) byte(w, n >> i);
}
size_t xbg_pack(uint8_t *out, size_t cap, const uint8_t mac[6], uint32_t mid,
                uint32_t uptime, const xbg_ad *ads, size_t count) {
    if (count > 210) return 0;
    writer w = {.p=out, .cap=cap};
    byte(&w, 0x85); /* v, mid, time, mac, devices */
    str(&w, "v"); byte(&w, 1);
    str(&w, "mid"); u32(&w, mid);
    str(&w, "time"); u32(&w, uptime);
    str(&w, "mac"); byte(&w, 0xc4); byte(&w, 6); raw(&w, mac, 6);
    str(&w, "devices"); byte(&w, 0xdc); byte(&w, count >> 8); byte(&w, count);
    for (size_t i = 0; i < count; ++i) {
        if (ads[i].len < 8 || ads[i].len > XBG_MAX_RECORD) return 0;
        byte(&w, 0xc4); byte(&w, ads[i].len); raw(&w, ads[i].data, ads[i].len);
    }
    return w.failed ? 0 : w.n;
}
const char *xbg_query_command(const char *name) {
    if (!strcmp(name, "version")) return "AT+VERS?\r\n";
    if (!strcmp(name, "address")) return "AT+ADDR?\r\n";
    if (!strcmp(name, "status")) return "AT\r\n";
    if (!strcmp(name, "help")) return "AT+HELP\r\n";
    if (!strcmp(name, "help-query")) return "AT+HELP?\r\n";
    if (!strcmp(name, "gatt-query")) return "AT+GATT?\r\n";
    /* Read-only status queries documented for the vendor's ZeroBeacon family.
       Probe for command reuse; this does not assume firmware compatibility. */
    if (!strcmp(name, "conn-query")) return "AT+CONN?\r\n";
    if (!strcmp(name, "role-query")) return "AT+ROLE?\r\n";
    if (!strcmp(name, "radd-query")) return "AT+RADD?\r\n";
    if (!strcmp(name, "rssi-query")) return "AT+RSSI?\r\n";
    return NULL;
}

/* Fixed identification requests only. No HCI reset, connection, firmware,
 * bootloader, mode-switch or arbitrary packet endpoint. H:5 SYNC can restart
 * an existing H:5 link, so use only while the scanner is deliberately paused. */
const uint8_t *xbg_query_bytes(const char *name, size_t *length) {
    static const uint8_t h5_sync[] = {0xc0,0x00,0x2f,0x00,0xd0,0x01,0x7e,0xc0};
    static const uint8_t h4_version[] = {0x01,0x01,0x10,0x00};
    if (!strcmp(name,"h5-sync")) { *length=sizeof(h5_sync);return h5_sync; }
    if (!strcmp(name,"h4-version")) { *length=sizeof(h4_version);return h4_version; }
    const char *text=xbg_query_command(name);
    *length=text ? strlen(text) : 0;
    return (const uint8_t *)text;
}
