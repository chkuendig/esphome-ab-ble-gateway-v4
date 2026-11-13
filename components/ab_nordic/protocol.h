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

/* Binary length, not CRLF, delimits advertisements: CRLF may occur in payload. */
xbg_event xbg_feed(xbg_parser *p, uint8_t byte, xbg_ad *ad,
                   char *line, size_t line_cap);
#endif
