#ifndef XBG_PROTOCOL_H
#define XBG_PROTOCOL_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#define XBG_MAX_AD 31
#define XBG_MAX_RECORD (8 + XBG_MAX_AD)
typedef struct { uint8_t data[XBG_MAX_RECORD]; uint8_t len; } xbg_ad;
typedef struct { uint8_t buf[160]; size_t used; uint32_t malformed; } xbg_parser;
typedef enum { XBG_NONE, XBG_AD, XBG_LINE } xbg_event;

/* Preserve binary query replies without interpreting them as AT or HCI. */
#define XBG_CAPTURE_BYTES 512
typedef struct { char hex[XBG_CAPTURE_BYTES * 2 + 1]; size_t total; } xbg_capture;
void xbg_capture_append(xbg_capture *capture, const uint8_t *bytes, size_t length);

/* Binary length, not CRLF, delimits advertisements: CRLF may occur in payload. */
xbg_event xbg_feed(xbg_parser *p, uint8_t byte, xbg_ad *ad,
                   char *line, size_t line_cap);
size_t xbg_pack(uint8_t *out, size_t cap, const uint8_t mac[6], uint32_t mid,
                uint32_t uptime, const xbg_ad *ads, size_t count);
const char *xbg_query_command(const char *name);
const uint8_t *xbg_query_bytes(const char *name, size_t *length);
#endif
