"""Extract auth token from a PCAP file."""
import subprocess, sys

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = sys.argv[1] if len(sys.argv) > 1 else r"C:\temp\grpc_live_test.pcapng"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "tcp.payload", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)

for line in r.stdout.splitlines()[:200]:
    parts = line.split("\t")
    if len(parts) < 2: continue
    try:
        d = bytes.fromhex(parts[1])
        idx = d.find(b'c0sh')
        if idx < 14: continue
        tag_pos = idx
        while tag_pos > 0 and d[tag_pos] != 0x0a: tag_pos -= 1
        if tag_pos == 0: continue
        length = 0; shift = 0; p = tag_pos + 1
        while p < len(d):
            b = d[p]; p += 1
            length |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        token = d[p:p+length]
        if len(token) >= 1500:
            sys.stdout.buffer.write(token)
            sys.exit(0)
    except: pass

sys.exit(1)
