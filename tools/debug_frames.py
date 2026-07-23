"""Debug: dump payload frames from capture to find auth token."""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_live_test.pcapng"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "tcp.payload", "-T", "fields",
     "-e", "frame.number", "-e", "tcp.payload"],
    capture_output=True, text=True
)

lines = r.stdout.splitlines()
print(f"Total payload frames: {len(lines)}")

for line in lines[:30]:
    parts = line.split("\t")
    if len(parts) >= 2:
        fnum = parts[0]
        try:
            d = bytes.fromhex(parts[1])
            # Check for HTTP/2 or gRPC data
            if b'LSDK' in d or b'grpc' in d or b'c0sh' in d:
                print(f"\nFrame {fnum} ({len(d)}B):")
                ascii = ''.join(chr(b) if 32<=b<127 else '.' for b in d[:200])
                print(f"  ASCII: {ascii[:200]}")
                print(f"  Hex: {d[:40].hex()}")
            elif len(d) > 100:
                print(f"\nFrame {fnum} ({len(d)}B): first 100 hex")
                print(f"  {d[:100].hex()}")
        except:
            pass
