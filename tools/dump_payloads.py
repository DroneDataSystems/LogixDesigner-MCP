"""Quick dump of TCP payload frames from capture."""
import subprocess, sys

PCAP = r"C:\temp\grpc_open_decode.pcapng"
TSHARK = r"C:\Program Files\Wireshark\tshark.exe"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "tcp.payload", "-T", "fields",
     "-e", "frame.number", "-e", "tcp.payload"],
    capture_output=True, text=True
)

lines = [l for l in r.stdout.splitlines() if l.strip()]
print(f"{len(lines)} TCP payload frames\n")

for line in lines[:20]:
    parts = line.split("\t")
    if len(parts) >= 2:
        fnum = parts[0]
        try:
            data = bytes.fromhex(parts[1])
            ascii = "".join(chr(b) if 32 <= b < 127 else "." for b in data[:200])
            # Show only frames with recognizable content
            if any(c.isalpha() for c in ascii[:50]):
                print(f"Frame {fnum}: {len(data)}B |{ascii[:150]}|")
        except:
            pass
