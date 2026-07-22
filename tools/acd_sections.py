"""ACD Section Table — full analysis."""
import struct

ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Palletizer_Test.ACD"
data = open(ACD, 'rb').read()

# Section table at 26861
TABLE_START = 26861
reserved = struct.unpack_from('<I', data, TABLE_START)[0]
section_count = struct.unpack_from('<I', data, TABLE_START + 4)[0]

print(f"Section table at {TABLE_START}, {section_count} entries")
print(f"Table size: {section_count * 8} bytes = {section_count * 8 / 1024:.1f} KB")

# Read ALL section entries (8 bytes each)
pos = TABLE_START + 8
all_sections = []
for _ in range(min(section_count, 4000)):
    if pos + 8 > len(data):
        break
    sec_id = struct.unpack_from('<I', data, pos)[0]
    sec_val = struct.unpack_from('<I', data, pos + 4)[0]
    all_sections.append((sec_id, sec_val))
    pos += 8

# Count by ID range
id_ranges = {}
for sid, sval in all_sections:
    bucket = sid // 100
    id_ranges[bucket] = id_ranges.get(bucket, 0) + 1

print(f"\nEntries by ID range:")
for bucket in sorted(id_ranges):
    print(f"  {bucket*100}-{bucket*100+99}: {id_ranges[bucket]} entries")

# Find where actual data starts (after section table)
data_start = TABLE_START + 8 + section_count * 8
print(f"\nSection data starts at offset: {data_start} (0x{data_start:x})")
print(f"Data size: {len(data) - data_start:,} bytes = {(len(data) - data_start) / 1024 / 1024:.1f} MB")

# Look at what follows the section table
post = data[data_start:data_start+256]
print(f"\nFirst 256 bytes of section data:")
print(f"  Hex: {post[:128].hex()}")
print(f"  ASCII: {''.join(chr(b) if 32<=b<127 else '.' for b in post[:128])}")

# Try to identify section boundaries
# Look for patterns that might indicate section markers
# Check if any sections have values that look like file offsets
possible_offsets = [sval for sid, sval in all_sections 
                    if data_start + 1000 < sval < len(data) - 100]
print(f"\nSections with values that look like file offsets (>{data_start}):")
for sid, sval in all_sections:
    if data_start + 1000 < sval < len(data) - 100:
        # Show context at that offset
        ctx = data[sval:sval+40]
        ascii_ctx = ''.join(chr(b) if 32<=b<127 else '.' for b in ctx)
        print(f"  Section {sid}: offset={sval} (0x{sval:x}) -> {ascii_ctx[:60]}")

# Also check sections with small values (counts)
small_counts = [(sid, sval) for sid, sval in all_sections if 1 <= sval <= 1000]
print(f"\nSections with small values (1-1000): {len(small_counts)}")
for sid, sval in small_counts[:20]:
    print(f"  Section {sid}: count={sval}")
