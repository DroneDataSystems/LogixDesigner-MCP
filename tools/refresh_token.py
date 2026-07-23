"""One-shot auth token capture — captures via tshark+SDK, writes TOKEN_FILE."""
import subprocess, sys, time, os

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
SERVICE = "LogixMCPServer"
TOKEN_FILE = r"C:\temp\grpc_auth_token.bin"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"
PCAP = r"C:\temp\grpc_auth_refresh.pcapng"

subprocess.run(["taskkill", "/F", "/IM", "tshark.exe"], capture_output=True)

cap = subprocess.Popen([TSHARK, "-i", "5", "-f", "tcp port 53204", "-w", PCAP],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(1)

# Restart SDK service to force fresh auth
subprocess.run(["sc", "stop", SERVICE], capture_output=True, timeout=30)
time.sleep(5)
subprocess.run(["sc", "start", SERVICE], capture_output=True, timeout=30)
time.sleep(12)

# Open project via SDK
sys.path.insert(0, r"C:\projects\LogixDesigner-MCP\src")
from logix_mcp.sdk_interop_real import RealSdkInterop
sdk = RealSdkInterop()
try:
    sdk.open_project(ACD)
    time.sleep(2)
    sdk.close_project()
    print("SDK_OK")
except Exception as e:
    print(f"SDK_ERROR: {e}")

cap.terminate(); cap.wait(timeout=5)

# Extract token
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
            with open(TOKEN_FILE, "wb") as f:
                f.write(token)
            print(f"TOKEN_OK:{len(token)}")
            sys.exit(0)
    except: pass

print("TOKEN_FAIL")
sys.exit(1)
