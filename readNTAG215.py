# https://www.securing.pl/en/how-mifare-classic-cards-work/

# upgrade to Python3 & add NTAG215 by WojciechGw
# 2026-04-03
#

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
# NTAG215: 135 pages (0-134), 4 bytes each, no authentication required.
for i in range(0, 135):
    page = pn532.ntag215_read_page(i)
    if page is None:
        # Retry once to rule out a transient error.
        page = pn532.ntag215_read_page(i)
        if page is None:
            print('Card removed from reader at page {0}!'.format(i))
            break
    ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in page)
    print("Page {0:03d}: 0x{1}  {2}".format(i, binascii.hexlify(page).decode(), ascii_repr))
