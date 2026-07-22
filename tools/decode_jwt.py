"""Decode the FactoryTalk JWT from the Open request."""
import subprocess, base64, json

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_open_decode.pcapng"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
d = bytes.fromhex(r.stdout.strip().split("\t")[-1])
proto = d[14:]  # skip HTTP/2 + gRPC headers

# Field 1: tag=0x0a, length varint=0xf80c (1656), value = 1656 bytes
tag = proto[0]  # 0x0a
lvar_len = 2
token = proto[1+lvar_len:1+lvar_len+1656]

print(f"Token length: {len(token)}")
print(f"Token start: {token[:80]}")
print(f"Token end: ...{token[-40:]}")
print()

# Try to decode as base64
try:
    decoded = base64.b64decode(token)
    print(f"Raw decoded ({len(decoded)} bytes): {decoded[:200]}")
except Exception as e:
    print(f"Base64 decode error: {e}")

# Also dump the next message (frame 16) to understand the streaming format
r2 = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==16", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
d2 = bytes.fromhex(r2.stdout.strip().split("\t")[-1])
grpc_data = d2[14:]  # skip HTTP/2 + gRPC

# Check for protobuf in frame 16
print(f"\nFrame 16 grpc payload: {len(grpc_data)}B")
print(f"First 20 bytes hex: {grpc_data[:20].hex()}")
# Parse fields
pos = 0
while pos < min(len(grpc_data), 30):
    tag = grpc_data[pos]
    if tag == 0:
        pos += 1
        continue
    field_num = tag >> 3
    wire_type = tag & 0x07
    pos += 1
    if wire_type == 2:
        length = 0; shift = 0
        while pos < len(grpc_data):
            b = grpc_data[pos]; pos += 1
            length |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        val = grpc_data[pos:pos+length]
        text_preview = val[:80]
        print(f"  Field {field_num} (string, {length}B): {text_preview}")
        break
