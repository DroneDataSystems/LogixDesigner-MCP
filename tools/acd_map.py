"""Map ACD section tags to L5K element counts."""
import struct

ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Palletizer_Test.ACD"
data = open(ACD, 'rb').read()

TABLE_START = 26861
pos = TABLE_START + 8

entries = []
while pos + 8 < len(data):
    sid = struct.unpack_from('<I', data, pos)[0]
    sval = struct.unpack_from('<I', data, pos + 4)[0]
    entries.append((sid, sval))
    pos += 8

# Extract single-byte tags (ASCII first byte, rest zeros)
tagged = {}
for sid, sval in entries:
    if sid < 256:  # Single byte IDs
        tagged[chr(sid)] = sval
    elif sid < 65536 and (sid & 0xFF) == 0:  # High byte + zeros
        tagged[chr(sid >> 8)] = sval

# Known L5K structure
l5k_stats = {
    'Programs': 11,
    'Routines': 83,
    'Tags': 5000,  # approximate
    'Modules': 10,
    'DataTypes': 20,  # approximate
}

print("Single-byte section tags:")
for code in sorted(tagged):
    val = tagged[code]
    if 1 <= val <= 50000:
        print(f"  '{code}' (0x{ord(code):02x}): value={val}")

print(f"\nL5K reference counts:")
for name, count in l5k_stats.items():
    print(f"  {name}: {count}")

# Try to identify tags by matching known counts
print(f"\n=== Candidate matches ===")
for name, count in l5k_stats.items():
    matches = [(code, val) for code, val in tagged.items() if val == count]
    if matches:
        print(f"  {name} ({count}): {matches}")
    else:
        close = [(code, val) for code, val in tagged.items() if abs(val - count) <= 3]
        if close:
            print(f"  {name} (~{count}): {close}")
