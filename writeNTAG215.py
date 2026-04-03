# upgrade for Python3 & add NTAG215 by WojciechGw
# 2026-04-03
#

# Based on original code from :
# Example of detecting and reading a block from a MiFare NFC card.
# Author: Manuel Fernando Galindo (mfg90@live.com)
#
# MIT License — see original header for full text.

import binascii
import math
import sys
import PN532

SERIAL_PORT = "COM8"

def make_ndef_text_pages(text, lang='en'):
    """Build NTAG215 page data for a single NDEF Text record (NFC Forum Well-Known Type 'T').

    NDEF Text record payload layout:
      [status_byte] [lang_bytes] [text_bytes_utf8]
      status_byte: bit7=0 (UTF-8), bits5-0 = len(lang)

    NDEF record:
      Short Record (SR=1, payload <= 255 bytes):
        D1 01 <payload_len> 54  <payload>
      Normal record (SR=0, payload > 255 bytes):
        C1 01 00 00 00 <payload_len_3bytes> 54  <payload>

    TLV wrapper on NTAG215 user memory (page 4+):
      03 <msg_len>     <ndef_record>  FE   (if msg_len <= 254)
      03 FF <hi> <lo>  <ndef_record>  FE   (if msg_len >= 255)

    Returns list of (page_number, bytearray(4)) starting at page 4.
    """
    lang_bytes = lang.encode('ascii')
    text_bytes = text.encode('utf-8')
    status = len(lang_bytes) & 0x3F        # UTF-8 flag=0, lang code length
    payload = bytes([status]) + lang_bytes + text_bytes

    if len(payload) <= 255:
        header = 0xD1                      # MB=1 ME=1 CF=0 SR=1 IL=0 TNF=001
        record = bytes([header, 0x01, len(payload), 0x54]) + payload
    else:
        header = 0xC1                      # MB=1 ME=1 CF=0 SR=0 IL=0 TNF=001
        plen = len(payload)
        record = (bytes([header, 0x01,
                         (plen >> 24) & 0xFF, (plen >> 16) & 0xFF,
                         (plen >> 8) & 0xFF, plen & 0xFF,
                         0x54]) + payload)

    msg_len = len(record)
    if msg_len <= 254:
        tlv = bytes([0x03, msg_len]) + record + bytes([0xFE])
    else:
        tlv = (bytes([0x03, 0xFF, (msg_len >> 8) & 0xFF, msg_len & 0xFF])
               + record + bytes([0xFE]))

    remainder = len(tlv) % 4
    if remainder:
        tlv += bytes(4 - remainder)        # pad last page with 0x00

    pages = []
    for i in range(0, len(tlv), 4):
        pages.append((4 + i // 4, bytearray(tlv[i:i+4])))
    return pages

# NTAG215 memory map:
#   Pages 0-3  : UID, lock bytes, capability container (read-only)
#   Pages 4-129: User memory (126 pages x 4 bytes = 504 bytes)
#   Pages 130-134: Config / lock / PWD / PACK
NTAG215_USER_PAGE_MIN = 4
NTAG215_USER_PAGE_MAX = 129

pn532 = PN532.PN532(SERIAL_PORT, 115200)
if not pn532.status:
    print('Error: serial port {0} is not available. Check connection and port name.'.format(SERIAL_PORT))
    sys.exit(1)
pn532.begin()
pn532.SAM_configuration()

ic, ver, rev, support = pn532.get_firmware_version()
print('Found PN532 with firmware version: {0}.{1}'.format(ver, rev))

# ── STEP 1: detect card ───────────────────────────────────────────────────────
print('')
print('NTAG215 Writer')
print('')
print('== STEP 1 =========================')
print('Place the NTAG215 card on the PN532...')
uid = pn532.read_passive_target()
while uid == "no_card":
    uid = pn532.read_passive_target()
print('')
print('Found card with UID: 0x{0}'.format(binascii.hexlify(uid)))
print('')
print('==============================================================')
print('WARNING: DO NOT REMOVE CARD FROM PN532 UNTIL FINISHED WRITING!')
print('==============================================================')

# ── STEP 2: write mode ────────────────────────────────────────────────────────
print('')
print('== STEP 2 =========================')
print('Write mode:')
print('  1. Single page  (4 bytes)')
print('  2. String       (multi-page, from start page)')
print('  3. NDEF Text record (NFC Forum Well-Known Type)')
print('')

mode = None
while mode is None:
    try:
        mode = int(input('Choose mode (1, 2 or 3): '))
        if mode not in (1, 2, 3):
            print('Error! Enter 1, 2 or 3.')
            mode = None
    except ValueError:
        print('Error! Enter a number.')

# ── STEP 3: data entry ────────────────────────────────────────────────────────
print('')
print('== STEP 3 =========================')

pages_to_write = []   # list of (page_number, bytearray(4))

if mode == 1:
    # ── Single page ──────────────────────────────────────────────────────────
    print('NTAG215 user pages: {0}-{1} (4 bytes each)'.format(
        NTAG215_USER_PAGE_MIN, NTAG215_USER_PAGE_MAX))
    print('')

    page_choice = None
    while page_choice is None:
        try:
            page_choice = int(input('Enter page number ({0}-{1}): '.format(
                NTAG215_USER_PAGE_MIN, NTAG215_USER_PAGE_MAX)))
            if page_choice not in range(NTAG215_USER_PAGE_MIN, NTAG215_USER_PAGE_MAX + 1):
                print('Error! Page must be between {0} and {1}.'.format(
                    NTAG215_USER_PAGE_MIN, NTAG215_USER_PAGE_MAX))
                page_choice = None
        except ValueError:
            print('Error! Enter a number.')

    print('')
    page_data = None
    while page_data is None:
        raw = input('Enter data (up to 4 ASCII chars or 8 hex digits): ').strip()
        if len(raw) == 8:
            try:
                page_data = bytearray(binascii.unhexlify(raw))
            except Exception:
                pass
        if page_data is None:
            if len(raw) > 4:
                print('Error! Max 4 ASCII characters or 8 hex digits.')
            else:
                page_data = bytearray(4)
                for i in range(len(raw)):
                    page_data[i] = ord(raw[i])

    ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in page_data)
    print('Data: 0x{0}  ({1})'.format(binascii.hexlify(page_data).decode(), ascii_repr))
    pages_to_write = [(page_choice, page_data)]

elif mode == 3:
    # ── NDEF Text record ─────────────────────────────────────────────────────
    lang = None
    while lang is None:
        raw_lang = input('Language code (2-8 ASCII chars, default "en"): ').strip()
        if raw_lang == '':
            raw_lang = 'en'
        try:
            raw_lang.encode('ascii')
        except UnicodeEncodeError:
            print('Error! Language code must be ASCII only.')
            continue
        if not (2 <= len(raw_lang) <= 8):
            print('Error! Language code must be 2-8 characters.')
            continue
        lang = raw_lang

    # overhead: TLV header (2) + NDEF record header (4) + status (1) + lang + terminator (1)
    overhead = 2 + 4 + 1 + len(lang.encode('ascii')) + 1
    max_text_bytes = (NTAG215_USER_PAGE_MAX - NTAG215_USER_PAGE_MIN + 1) * 4 - overhead

    text = None
    while text is None:
        text = input('Enter text (max ~{0} UTF-8 bytes): '.format(max_text_bytes))
        if len(text) == 0:
            print('Error! Text cannot be empty.')
            text = None
            continue
        encoded = text.encode('utf-8')
        if len(encoded) > max_text_bytes:
            print('Error! Text too long ({0} bytes UTF-8, max {1}).'.format(
                len(encoded), max_text_bytes))
            text = None

    pages_to_write = make_ndef_text_pages(text, lang)
    total_bytes = len(pages_to_write) * 4
    print('')
    print('NDEF Text record: lang="{0}", text={1} UTF-8 bytes'.format(
        lang, len(text.encode('utf-8'))))
    print('TLV+NDEF: {0} bytes → {1} pages (4-{2})'.format(
        total_bytes, len(pages_to_write), 3 + len(pages_to_write)))

else:
    # ── String from start page ───────────────────────────────────────────────
    max_bytes = (NTAG215_USER_PAGE_MAX - NTAG215_USER_PAGE_MIN + 1) * 4  # 504

    start_page = None
    while start_page is None:
        try:
            start_page = int(input('Enter start page ({0}-{1}): '.format(
                NTAG215_USER_PAGE_MIN, NTAG215_USER_PAGE_MAX)))
            if start_page not in range(NTAG215_USER_PAGE_MIN, NTAG215_USER_PAGE_MAX + 1):
                print('Error! Page must be between {0} and {1}.'.format(
                    NTAG215_USER_PAGE_MIN, NTAG215_USER_PAGE_MAX))
                start_page = None
        except ValueError:
            print('Error! Enter a number.')

    pages_available = NTAG215_USER_PAGE_MAX - start_page + 1
    max_chars = pages_available * 4
    print('Pages available from {0}: {1}  (max {2} characters)'.format(
        start_page, pages_available, max_chars))
    print('')

    text = None
    while text is None:
        text = input('Enter string (max {0} chars): '.format(max_chars))
        if len(text) == 0:
            print('Error! String cannot be empty.')
            text = None
        elif len(text) > max_chars:
            print('Error! String too long ({0} chars), max {1} for start page {2}.'.format(
                len(text), max_chars, start_page))
            text = None

    # Split string into 4-byte pages, pad last page with 0x00
    pages_needed = math.ceil(len(text) / 4)
    raw_bytes = bytearray(text.encode('ascii', errors='replace'))
    raw_bytes += bytearray(pages_needed * 4 - len(raw_bytes))  # pad to full pages

    for i in range(pages_needed):
        chunk = raw_bytes[i*4 : i*4+4]
        pages_to_write.append((start_page + i, bytearray(chunk)))

    print('')
    print('Pages to write: {0}-{1}  ({2} pages, {3} bytes)'.format(
        start_page, start_page + pages_needed - 1, pages_needed, pages_needed * 4))

# ── STEP 4: preview & confirm ─────────────────────────────────────────────────
print('')
print('== STEP 4 =========================')
print('Preview:')
for page_num, data in pages_to_write:
    ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    print('  Page {0:03d}: 0x{1}  {2}'.format(
        page_num, binascii.hexlify(data).decode(), ascii_repr))
print('')
confirm = input('Confirm write (Y/N)? ')
if confirm.strip().lower() not in ('y', 'yes'):
    print('Aborted!')
    sys.exit(0)

# ── STEP 5: write ─────────────────────────────────────────────────────────────
print('')
print('Writing... (DO NOT REMOVE CARD)')

# Re-select the card before writing — ISO 14443 active state may have been
# lost during user interaction. Re-detection re-activates the card in the PN532.
uid = pn532.read_passive_target()
if uid == "no_card":
    print('Error! Card not found. Place the card back on the PN532.')
    sys.exit(-1)

for page_num, data in pages_to_write:
    if not pn532.ntag215_write_page(page_num, data):
        print('Error! Failed to write page {0} (card removed?).'.format(page_num))
        sys.exit(-1)
    print('  Page {0:03d} written.'.format(page_num))

print('')
print('Done! {0} page(s) written. You may remove the card.'.format(len(pages_to_write)))
