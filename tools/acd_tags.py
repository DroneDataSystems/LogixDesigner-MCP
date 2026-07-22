"""Decode ACD section IDs as 4-char ASCII tags."""
import struct

ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Palletizer_Test.ACD"
data = open(ACD, 'rb').read()

TABLE_START = 26861
pos = TABLE_START + 8

# Read ALL section entries
entries = []
while pos + 8 < len(data):
    sid = struct.unpack_from('<I', data, pos)[0]
    sval = struct.unpack_from('<I', data, pos + 4)[0]
    entries.append((sid, sval))
    pos += 8

# Decode ASCII-tagged sections (IDs that look like 4-char codes)
ascii_tags = []
for sid, sval in entries:
    # Check if all 4 bytes are printable ASCII
    b = struct.pack('<I', sid)
    if all(32 <= c < 127 or c == 0 for c in b):
        tag = ''.join(chr(c) if 32 <= c < 127 else f'\\x{c:02x}' for c in b)
        ascii_tags.append((tag, sid, sval))

print(f"{len(ascii_tags)} ASCII-tagged sections:")
for tag, sid, sval in ascii_tags[:50]:
    print(f"  '{tag}' = 0x{sid:08x}  val={sval}")
