"""ACD Binary Format Analyzer — map sections to L5K elements."""
import struct, sys, os

ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Palletizer_Test.ACD"

def read_acd(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()

data = read_acd(ACD)
print(f"File: {os.path.basename(ACD)}")
print(f"Size: {len(data):,} bytes")

# Find text header boundary
end_header = data.find(b'\x00\x00\x00', 100)
print(f"Text header ends at offset: {end_header}")

# Read the text header
header_text = data[:end_header].decode('utf-8', errors='replace')
# Extract key metadata from header
for line in header_text.split('\r\n')[:15]:
    if line.strip():
        print(f"  Header: {line.strip()}")

# Section table starts at end_header
print(f"\n=== Section Table (offset {end_header}) ===")

# First 4 bytes: reserved/version
reserved = struct.unpack_from('<I', data, end_header)[0]
print(f"  Reserved: {reserved}")

# Next 4 bytes: section count or total sections
section_count = struct.unpack_from('<I', data, end_header + 4)[0]
print(f"  Section count/value: {section_count} (0x{section_count:04x})")

# Read section entries
# Each entry: [4-byte section_id][4-byte value]
pos = end_header + 8
sections = []
max_sections = min(section_count, 50)  # Read up to 50
for _ in range(max_sections):
    if pos + 8 > len(data):
        break
    sec_id = struct.unpack_from('<I', data, pos)[0]
    sec_val = struct.unpack_from('<I', data, pos + 4)[0]
    sections.append((sec_id, sec_val))
    pos += 8
    
    if sec_id == 0 and sec_val == 0:
        break

print(f"\n  Read {len(sections)} section entries:")
for i, (sid, sval) in enumerate(sections[:30]):
    marker = ""
    if 1 <= sid <= 20:
        marker = f"  # Section {sid}"
    print(f"    [{i:3d}] id={sid:4d} (0x{sid:04x})  val={sval:10d} (0x{sval:08x}){marker}")

# Try to find text references for known L5K elements
print(f"\n=== Searching for L5K element references ===")
search_terms = [
    (b'IE_VER', 'IE_VER'),
    (b'CONTROLLER', 'Controller name'),
    (b'PROGRAM', 'Program start'),
    (b'ROUTINE', 'Routine start'),
    (b'\x00Mativ', 'Mativ string'),
    (b'Palletizer', 'Palletizer'),
]
for term, label in search_terms:
    idx = data.find(term, end_header)
    if idx >= 0:
        ctx = data[max(0,idx-4):idx+60]
        # Try to show readable portion
        readable = ""
        for b in ctx:
            if 32 <= b < 127:
                readable += chr(b)
            elif b == 0:
                readable += "."
            else:
                readable += f"\\x{b:02x}"
        print(f"  {label} at {idx}: ...{readable[:80]}...")
    else:
        print(f"  {label}: not found")

# Analyze binary structure after section table
# The section table might be followed by the actual section data
# Let's look at what comes after the section entries
pos_after_table = pos
print(f"\n=== Data after section table (at {pos_after_table}) ===")
post_data = data[pos_after_table:pos_after_table+256]
print(f"  First 128 bytes hex: {post_data[:128].hex()}")
print(f"  First 128 ASCII: {''.join(chr(b) if 32<=b<127 else '.' for b in post_data[:128])}")
