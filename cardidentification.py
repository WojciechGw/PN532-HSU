# NFC card type identification script.
# Detects card family from ATQA + SAK, then uses GET_VERSION for NTAG subtype.

import binascii
import PN532

SERIAL_PORT = "COM8"

# Card type table keyed by (atqa_byte0, atqa_byte1, sak).
# PN532 returns ATQA as a big-endian 16-bit value (high byte first),
# matching the value printed by binascii.hexlify, e.g. "0044" → [0x00, 0x44].
CARD_TYPES = {
    (0x00, 0x44, 0x00): 'NTAG / MiFare Ultralight',   # ATQA=0x0044
    (0x00, 0x04, 0x08): 'MiFare Classic 1K',            # ATQA=0x0004
    (0x00, 0x02, 0x18): 'MiFare Classic 4K',            # ATQA=0x0002
    (0x00, 0x04, 0x09): 'MiFare Classic Mini',          # ATQA=0x0004
    (0x00, 0x04, 0x10): 'MiFare Plus 2K SL2',           # ATQA=0x0004
    (0x00, 0x02, 0x11): 'MiFare Plus 4K SL2',           # ATQA=0x0002
    (0x00, 0x04, 0x20): 'MiFare Plus 2K SL3',           # ATQA=0x0004
    (0x00, 0x02, 0x20): 'MiFare Plus 4K SL3',           # ATQA=0x0002
    (0x03, 0x44, 0x20): 'MiFare DESFire',               # ATQA=0x0344
}

# GET_VERSION storage size byte → NTAG subtype
NTAG_STORAGE_SIZE = {
    0x0F: 'NTAG213  (144 bytes user memory)',
    0x11: 'NTAG215  (504 bytes user memory)',
    0x13: 'NTAG216  (888 bytes user memory)',
}

pn532 = PN532.PN532(SERIAL_PORT, 115200)
pn532.begin()
pn532.SAM_configuration()

ic, ver, rev, support = pn532.get_firmware_version()
print('Found PN532 with firmware version: {0}.{1}'.format(ver, rev))
print('')
print('Waiting for NFC card...')

result = pn532.read_passive_target_with_info()
while result == "no_card":
    result = pn532.read_passive_target_with_info()

atqa, sak, uid = result

print('--- Card detected ---')
print('UID  : 0x{0} ({1} bytes)'.format(binascii.hexlify(uid).decode(), len(uid)))
print('ATQA : 0x{0}'.format(binascii.hexlify(atqa).decode()))
print('SAK  : 0x{0:02X}'.format(sak))

card_type = CARD_TYPES.get((atqa[0], atqa[1], sak), 'Unknown card type')
print('Type : {0}'.format(card_type))

# For NTAG/Ultralight family (ATQA=0x4400, SAK=0x00) try GET_VERSION
# to distinguish exact NTAG model from MiFare Ultralight.
if atqa[0] == 0x00 and atqa[1] == 0x44 and sak == 0x00:
    version = pn532.ntag_get_version()
    if version is None:
        print('Subtype: MiFare Ultralight (GET_VERSION not supported)')
    else:
        storage_size = version[6]
        subtype = NTAG_STORAGE_SIZE.get(storage_size,
                  'NTAG (unknown storage size 0x{0:02X})'.format(storage_size))
        print('Subtype: {0}'.format(subtype))
