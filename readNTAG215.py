# upgrade for Python3 & add NTAG215 by WojciechGw
# 2026-04-03
#
# Based on original code from :
# Example of detecting and reading a block from a MiFare NFC card.
# Author: Manuel Fernando Galindo (mfg90@live.com)
#
# Copyright (c) 2016 Manuel Fernando Galindo
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import binascii
import sys
import time
import PN532


def parse_ndef_text(data):
    """Parse NDEF Text records from NTAG215 user memory bytes.

    data: bytes/bytearray starting at page 4 (beginning of user memory).
    Returns list of (lang, text) tuples, one per Text record found.

    TLV wrapper: 03 <len> <ndef_msg> FE
    NDEF record header byte: MB ME CF SR IL TNF[2:0]
    Text record payload: [status] [lang_ascii] [text_utf8_or_utf16]
      status bit7: 0=UTF-8  1=UTF-16
      status bits5-0: lang code length
    """
    results = []
    i = 0
    while i < len(data):
        if i >= len(data):
            break
        tlv_type = data[i]; i += 1
        if tlv_type == 0x00:    # NULL — padding, skip
            continue
        if tlv_type == 0xFE:    # Terminator
            break
        if i >= len(data):
            break
        length = data[i]; i += 1
        if length == 0xFF:      # 3-byte length
            if i + 2 > len(data):
                break
            length = (data[i] << 8) | data[i + 1]; i += 2
        if tlv_type != 0x03:    # not NDEF Message — skip value
            i += length
            continue
        # ── Parse NDEF message ────────────────────────────────────────────
        msg_end = i + length
        while i < msg_end and i < len(data):
            record_header = data[i]; i += 1
            tnf      = record_header & 0x07
            sr       = (record_header >> 4) & 0x01   # Short Record flag
            il       = (record_header >> 3) & 0x01   # ID Length present flag
            if i >= len(data): break
            type_len = data[i]; i += 1
            if sr:
                if i >= len(data): break
                payload_len = data[i]; i += 1
            else:
                if i + 4 > len(data): break
                payload_len = ((data[i] << 24) | (data[i+1] << 16) |
                               (data[i+2] << 8) | data[i+3]); i += 4
            if il:
                if i >= len(data): break
                id_len = data[i]; i += 1
            else:
                id_len = 0
            rec_type = bytes(data[i:i + type_len]); i += type_len
            i += id_len
            payload  = bytes(data[i:i + payload_len]); i += payload_len
            # ── Text record: TNF=0x01, type=b'T' ─────────────────────────
            if tnf == 0x01 and rec_type == b'\x54' and len(payload) >= 1:
                status   = payload[0]
                encoding = 'utf-16' if (status & 0x80) else 'utf-8'
                lang_len = status & 0x3F
                lang     = payload[1:1 + lang_len].decode('ascii', errors='replace')
                text     = payload[1 + lang_len:].decode(encoding, errors='replace')
                results.append((lang, text))
        i = msg_end
    return results


SERIAL_PORT = "COM8"

# Create an instance of the PN532 class.
pn532 = PN532.PN532(SERIAL_PORT, 115200)

# Call begin to initialize communication with the PN532.  Must be done before
# any other calls to the PN532!
pn532.begin()

# Configure PN532 to communicate with MiFare cards.
pn532.SAM_configuration()

# Get the firmware version from the chip and print(it out.)
ic, ver, rev, support = pn532.get_firmware_version()
print('Found PN532 with firmware version: {0}.{1}'.format(ver, rev))


print('Waiting for NTAG215 card...')
uid = pn532.read_passive_target()
while uid == "no_card":
    uid = pn532.read_passive_target()
print('Found card with UID: 0x{0}'.format(binascii.hexlify(uid)))

print('')
print('Display mode:')
print('  1. Page list  (hex + ASCII per page)')
print('  2. Progress bar')
print('')
display_mode = None
while display_mode is None:
    try:
        display_mode = int(input('Choose display mode (1 or 2): '))
        if display_mode not in (1, 2):
            print('Error! Enter 1 or 2.')
            display_mode = None
    except ValueError:
        print('Error! Enter a number.')
print('')

TOTAL_PAGES = 135
# NTAG215: 135 pages (0-134), 4 bytes each, no authentication required.
user_memory = bytearray()   # pages 4-129 collected for NDEF parsing
all_pages = {}              # page_number → bytearray(4), used for post-read list
for i in range(0, TOTAL_PAGES):
    page = pn532.ntag215_read_page(i)
    if page is None:
        # Retry once to rule out a transient error.
        page = pn532.ntag215_read_page(i)
        if page is None:
            if display_mode == 2:
                print('')
            print('Card removed from reader at page {0}!'.format(i))
            break
    all_pages[i] = page
    if display_mode == 1:
        ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in page)
        print("Page {0:03d}: 0x{1}  {2}".format(i, binascii.hexlify(page).decode(), ascii_repr))
    else:
        filled = (i + 1) * 40 // TOTAL_PAGES
        bar = '#' * filled + '-' * (40 - filled)
        print('\rReading: [{0}] {1:3d}/{2}'.format(bar, i + 1, TOTAL_PAGES), end='', flush=True)
    if 4 <= i <= 129:
        user_memory += page

if display_mode == 2:
    print('')
    show_list = input('Show page list? (Y/N): ').strip().lower()
    if show_list in ('y', 'yes'):
        print('')
        for idx in sorted(all_pages):
            page = all_pages[idx]
            ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in page)
            print("Page {0:03d}: 0x{1}  {2}".format(idx, binascii.hexlify(page).decode(), ascii_repr))

# ── NDEF Text records ─────────────────────────────────────────────────────────
print('')
ndef_records = parse_ndef_text(user_memory)
if ndef_records:
    print('NDEF Text record(s) found: {0}'.format(len(ndef_records)))
    for idx, (lang, text) in enumerate(ndef_records):
        print('  [{0}] lang="{1}"  text="{2}"'.format(idx + 1, lang, text))
else:
    print('No NDEF Text records found.')
