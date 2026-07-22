"""Decode the Open gRPC request protobuf from capture — corrected offsets."""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_open_decode.pcapng"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
hexdata = r.stdout.strip().split("\t")[-1]
data = bytes.fromhex(hexdata)

# HTTP/2 DATA frame: 3B length + 1B type + 1B flags + 4B stream_id = 9 bytes
# gRPC frame: 1B compression + 4B message_length = 5 bytes
# Total header: 14 bytes
proto = data[14:]

# Parse protobuf
pos = 0
field_count = 0
while pos < len(proto) and field_count < 20:
    if pos >= len(proto):
        break
    
    tag_byte = proto[pos]
    field_num = tag_byte >> 3
    wire_type = tag_byte & 0x07
    
    # Skip zero bytes (padding/alignment at end of message)
    if tag_byte == 0:
        remaining = proto[pos:]
        if all(b == 0 for b in remaining[:10]):
            print(f"  ({len(remaining)} bytes of zero padding at end)")
            break
        else:
            pos += 1
            continue
    
    pos += 1
    field_count += 1

    wire_names = {0: "varint", 1: "fixed64", 2: "length-delimited", 3: "start_group", 4: "end_group", 5: "fixed32"}
    wn = wire_names.get(wire_type, f"type_{wire_type}")

    if wire_type == 0:  # varint
        value = 0; shift = 0
        while pos < len(proto):
            b = proto[pos]; pos += 1
            value |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        print(f"  Field {field_num} (varint): {value}")

    elif wire_type == 2:  # length-delimited
        length = 0; shift = 0
        while pos < len(proto):
            b = proto[pos]; pos += 1
            length |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        if pos + length > len(proto):
            print(f"  Field {field_num} ({wn}, {length}B) — truncated ({pos+length} > {len(proto)})")
            break
        value = proto[pos:pos+length]
        pos += length
        try:
            text = value.decode('utf-8')
            if len(text) <= 120:
                print(f"  Field {field_num} (string, {length}B): {text}")
            else:
                print(f"  Field {field_num} (string, {length}B): {text[:60]}...{text[-20:]}")
        except:
            print(f"  Field {field_num} (bytes, {length}B): {value[:50].hex()}...")

    elif wire_type == 1:  # fixed64
        if pos + 8 > len(proto): break
        value = int.from_bytes(proto[pos:pos+8], 'little')
        pos += 8
        print(f"  Field {field_num} (fixed64): {value}")

    elif wire_type == 5:  # fixed32
        if pos + 4 > len(proto): break
        value = int.from_bytes(proto[pos:pos+4], 'little')
        pos += 4
        print(f"  Field {field_num} (fixed32): {value}")

    else:
        print(f"  Field {field_num} ({wn}) — stopping")
        break

# Also check the chunk frames (16, 18, 20...) to see the ACD data streaming format
print("\n--- Checking ACD data chunks ---")
for fn in [16, 18, 20]:
    r2 = subprocess.run(
        [TSHARK, "-r", PCAP, "-Y", f"frame.number=={fn}", "-T", "fields", "-e", "tcp.payload"],
        capture_output=True, text=True
    )
    hd = r2.stdout.strip().split("\t")[-1]
    if hd:
        d = bytes.fromhex(hd)
        # Look for ACD text header
        if b"This file" in d or b"RSLogix" in d:
            idx = d.find(b"This file")
            print(f"  Frame {fn}: ACD text header found at offset {idx}:")
            print(f"    {d[idx:idx+80]}")
