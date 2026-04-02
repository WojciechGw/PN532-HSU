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
import PN532


SERIAL_PORT = "COM8"

# NTAG215 memory map:
#   Pages 0-3  : UID, lock bytes, capability container (read-only)
#   Pages 4-129: User memory (126 pages x 4 bytes = 504 bytes)
#   Pages 130-134: Config / lock / PWD / PACK
NTAG215_USER_PAGE_MIN = 4
NTAG215_USER_PAGE_MAX = 129

pn532 = PN532.PN532(SERIAL_PORT, 115200)
pn532.begin()
pn532.SAM_configuration()

ic, ver, rev, support = pn532.get_firmware_version()
print('Found PN532 with firmware version: {0}.{1}'.format(ver, rev))

# Step 1 — detect card
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
print('')

# Step 2 — choose page and data
print('== STEP 2 =========================')
print('NTAG215 user pages: {0}-{1} (4 bytes each)'.format(NTAG215_USER_PAGE_MIN, NTAG215_USER_PAGE_MAX))
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
    raw = input('Enter data (up to 4 ASCII chars or 8 hex digits, e.g. "AB12" or hex "41423132"): ')
    raw = raw.strip()
    # Try hex input first (exactly 8 hex digits)
    if len(raw) == 8:
        try:
            page_data = bytearray(binascii.unhexlify(raw))
        except Exception:
            pass
    # Fall back to ASCII (up to 4 chars, pad with 0x00)
    if page_data is None:
        if len(raw) > 4:
            print('Error! Max 4 ASCII characters or 8 hex digits.')
        else:
            page_data = bytearray(4)
            for i in range(len(raw)):
                page_data[i] = ord(raw[i])
    if page_data is not None:
        print('Data to write: 0x{0}  ({1})'.format(
            binascii.hexlify(page_data).decode(),
            ''.join(chr(b) if 32 <= b < 127 else '.' for b in page_data)))

# Step 3 — confirm and write
print('')
print('== STEP 3 =========================')
print('Page : {0}'.format(page_choice))
print('Data : 0x{0}'.format(binascii.hexlify(page_data).decode()))
print('')
confirm = input('Confirm write (Y/N)? ')
if confirm.strip().lower() not in ('y', 'yes'):
    print('Aborted!')
    sys.exit(0)

print('Writing page {0}... (DO NOT REMOVE CARD)'.format(page_choice))
if not pn532.ntag215_write_page(page_choice, page_data):
    print('Error! Failed to write page {0}.'.format(page_choice))
    sys.exit(-1)
print('Page {0} written successfully! You may remove the card.'.format(page_choice))
