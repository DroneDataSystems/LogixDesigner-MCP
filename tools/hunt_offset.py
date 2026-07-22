"""Find correct protobuf offset by dumping frame bytes with annotations."""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_open_decode.pcapng"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
hexdata = r.stdout.strip().split("\t")[-1]
data = bytes.fromhex(hexdata)

print(f"Frame 14: {len(data)} bytes total\n")

# Annotate each byte
for i, b in enumerate(data[:100]):
    ch = chr(b) if 32 <= b < 127 else "."
    print(f"  [{i:3d}] 0x{b:02x} {ch:3s}  ", end="")
    if i == 0: print("← HTTP/2 DATA frame: length byte 1")
    elif i == 1: print("← length byte 2")
    elif i == 2: print("← length byte 3")
    elif i == 3: print("← frame type (0x00 = DATA)")
    elif i == 4: print("← flags (0x01 = END_STREAM)")
    elif i == 5: print("← stream ID byte 1")
    elif i == 6: print("← stream ID byte 2")
    elif i == 7: print("← stream ID byte 3")
    elif i == 8: print("← stream ID byte 4")
    elif i == 9: print("← gRPC: compression flag (0x00)")
    elif i == 10: print("← gRPC: message length byte 1")
    elif i == 11: print("← length byte 2")
    elif i == 12: print("← length byte 3")
    elif i == 13: print("← length byte 4")
    elif i == 14: print("← PROTO START? 0x00")
    elif 15 <= i <= 21: print("")  # unknown prefix
    elif i == 22: print("← 0x7b = field 15, wire 3?")
    elif i >= 23: print("")
    else:
        print()
