"""Decode the Open gRPC request protobuf from capture."""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_open_decode.pcapng"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
hexdata = r.stdout.strip().split("\t")[-1]
data = bytes.fromhex(hexdata)

# Skip HTTP/2 DATA frame header (9 bytes), then gRPC header (5 bytes)
proto = data[14:]

# Parse protobuf
pos = 0
while pos < len(proto):
    tag = proto[pos]
    field_num = tag >> 3
    wire_type = tag & 0x07
    pos += 1

    if wire_type == 0:  # varint
        value = 0; shift = 0
        while pos < len(proto):
            b = proto[pos]; pos += 1
            value |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        print(f"Field {field_num} (varint): {value}")
    elif wire_type == 2:  # length-delimited
        length = 0; shift = 0
        while pos < len(proto):
            b = proto[pos]; pos += 1
            length |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        value = proto[pos:pos+length]; pos += length
        try:
            text = value.decode('utf-8')
            preview = text if len(text) <= 100 else text[:80] + "..."
            print(f"Field {field_num} (string, {length}B): {preview}")
        except:
            print(f"Field {field_num} (bytes, {length}B): {value[:40].hex()}...")
    else:
        print(f"Field {field_num} (wire_type {wire_type}) — unknown")
        break
