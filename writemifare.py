# MiFare Classic NFC card writer.
# Author: Manuel Fernando Galindo (mfg90@live.com) — extended for block types.
#
# MIT License — see original header for full text.

import binascii
import sys
import struct
import PN532

CARD_KEY    = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
SERIAL_PORT = "COM8"

# Sector trailer blocks for MiFare Classic 1K: every 4th block starting at 3.
SECTOR_TRAILERS = set(range(3, 64, 4))   # {3, 7, 11, ..., 63}

BLOCK_TYPES = {
    1: ('Text',           'Up to 16 ASCII characters, padded with 0x00'),
    2: ('Hex data',       '32 hex digits = 16 raw bytes'),
    3: ('Value block',    '32-bit signed integer with MiFare redundancy bytes'),
    4: ('Sector trailer', 'Key A (6B) + Access bits + Key B (6B)  [DANGEROUS]'),
}


def make_value_block(value, block_number):
    """Build a 16-byte MiFare Classic value block.

    Format:
      Bytes  0- 3: value (int32, little-endian)
      Bytes  4- 7: ~value (bitwise complement, error detection)
      Bytes  8-11: value (redundant copy)
      Byte  12: block address
      Byte  13: ~block address
      Byte  14: block address
      Byte  15: ~block address
    """
    v     = struct.pack('<i', value)
    inv_v = bytes([~b & 0xFF for b in v])
    addr  = block_number & 0xFF
    return bytearray(v + inv_v + v + bytes([addr, ~addr & 0xFF, addr, ~addr & 0xFF]))


def input_hex_key(prompt, default='FFFFFFFFFFFF'):
    """Read a 6-byte key as 12 hex digits."""
    while True:
        raw = input('{0} [default {1}]: '.format(prompt, default)).strip()
        if raw == '':
            raw = default
        if len(raw) == 12:
            try:
                return list(binascii.unhexlify(raw))
            except Exception:
                pass
        print('Error! Enter exactly 12 hex digits (e.g. FFFFFFFFFFFF).')


# ── Init ──────────────────────────────────────────────────────────────────────
pn532 = PN532.PN532(SERIAL_PORT, 115200)
pn532.begin()
pn532.SAM_configuration()

ic, ver, rev, support = pn532.get_firmware_version()
print('Found PN532 with firmware version: {0}.{1}'.format(ver, rev))

# ── STEP 1: detect card ───────────────────────────────────────────────────────
print('')
print('MiFare Classic Writer')
print('')
print('== STEP 1 =========================')
print('Place the MiFare Classic card on the PN532...')
uid = pn532.read_passive_target()
while uid == "no_card":
    uid = pn532.read_passive_target()
print('')
print('Found card with UID: 0x{0}'.format(binascii.hexlify(uid)))
print('')
print('==============================================================')
print('WARNING: DO NOT REMOVE CARD FROM PN532 UNTIL FINISHED WRITING!')
print('==============================================================')

# ── STEP 2: block number ──────────────────────────────────────────────────────
print('')
print('== STEP 2 =========================')
print('MiFare Classic 1K blocks: 1-62  (block 0 = manufacturer, read-only)')
print('Sector trailers (keys/ACL): 3, 7, 11, 15 ... 63')
print('')

block_choice = None
while block_choice is None:
    try:
        block_choice = int(input('Enter block number (1-62): '))
        if block_choice < 1 or block_choice > 62:
            print('Error! Block must be between 1 and 62.')
            block_choice = None
        elif block_choice in SECTOR_TRAILERS:
            print('WARNING: Block {0} is a sector trailer — writing wrong access bits can lock the card!'.format(block_choice))
            if input('Continue? (Y/N): ').strip().lower() not in ('y', 'yes'):
                block_choice = None
    except ValueError:
        print('Error! Enter a number.')

# ── STEP 3: block type ────────────────────────────────────────────────────────
print('')
print('== STEP 3 =========================')
print('Available block types:')
for num, (name, desc) in BLOCK_TYPES.items():
    print('  {0}. {1:<16} {2}'.format(num, name, desc))
print('')

type_choice = None
while type_choice is None:
    try:
        type_choice = int(input('Choose type (1-{0}): '.format(len(BLOCK_TYPES))))
        if type_choice not in BLOCK_TYPES:
            print('Error! Enter a number between 1 and {0}.'.format(len(BLOCK_TYPES)))
            type_choice = None
    except ValueError:
        print('Error! Enter a number.')

# ── STEP 4: data entry ────────────────────────────────────────────────────────
print('')
print('== STEP 4 =========================')
block_data = None

if type_choice == 1:                        # ── Text
    raw = input('Enter text (up to 16 chars): ')[:16]
    block_data = bytearray(16)
    for i, c in enumerate(raw):
        block_data[i] = ord(c)
    ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in block_data)
    print('Data: 0x{0}  "{1}"'.format(binascii.hexlify(block_data).decode(), ascii_repr))

elif type_choice == 2:                      # ── Hex
    while block_data is None:
        raw = input('Enter 32 hex digits: ').strip()
        if len(raw) == 32:
            try:
                block_data = bytearray(binascii.unhexlify(raw))
            except Exception:
                print('Error! Invalid hex string.')
        else:
            print('Error! Must be exactly 32 hex digits.')
    print('Data: 0x{0}'.format(binascii.hexlify(block_data).decode()))

elif type_choice == 3:                      # ── Value block
    while block_data is None:
        try:
            value = int(input('Enter 32-bit signed integer (-2147483648 to 2147483647): '))
            if -2147483648 <= value <= 2147483647:
                block_data = make_value_block(value, block_choice)
                print('Value: {0}'.format(value))
                print('Data:  0x{0}'.format(binascii.hexlify(block_data).decode()))
            else:
                print('Error! Value out of 32-bit signed integer range.')
        except ValueError:
            print('Error! Enter an integer.')

elif type_choice == 4:                      # ── Sector trailer
    print('Enter keys as 12 hex digits (e.g. FFFFFFFFFFFF = default):')
    key_a = input_hex_key('Key A')
    key_b = input_hex_key('Key B')
    # Access bits: FF 07 80 = transport configuration (full access with Key A/B).
    # GPB (general purpose byte): 0x69 (NXP default).
    access = [0xFF, 0x07, 0x80]
    gpb    = 0x69
    block_data = bytearray(key_a + access + [gpb] + key_b)
    print('Data: 0x{0}'.format(binascii.hexlify(block_data).decode()))

# ── STEP 5: confirm and write ─────────────────────────────────────────────────
print('')
print('== STEP 5 =========================')
print('Block : {0}'.format(block_choice))
print('Type  : {0}'.format(BLOCK_TYPES[type_choice][0]))
print('Data  : 0x{0}'.format(binascii.hexlify(block_data).decode()))
print('')
confirm = input('Confirm write (Y/N)? ')
if confirm.strip().lower() not in ('y', 'yes'):
    print('Aborted!')
    sys.exit(0)

print('Writing block {0}... (DO NOT REMOVE CARD)'.format(block_choice))

if not pn532.mifare_classic_authenticate_block(uid, block_choice, PN532.MIFARE_CMD_AUTH_B, CARD_KEY):
    print('Error! Failed to authenticate block {0}.'.format(block_choice))
    sys.exit(-1)

if not pn532.mifare_classic_write_block(block_choice, block_data):
    print('Error! Failed to write block {0}.'.format(block_choice))
    sys.exit(-1)

print('Block {0} written successfully! You may remove the card.'.format(block_choice))
