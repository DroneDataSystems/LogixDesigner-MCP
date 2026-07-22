"""Extract live FactoryTalk auth token by capturing a quick Open call."""
import subprocess, time, sys, os

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_live_auth.pcapng"
PROJECT = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"

# Add SDK to path
sys.path.insert(0, r"C:\projects\LogixDesigner-MCP\src")

# 1. Close any open project to ensure fresh connection
from logix_mcp.sdk_interop_real import RealSdkInterop
sdk = RealSdkInterop()
try:
    sdk.close_project()
except:
    pass

# 2. Start capture
print("Starting capture...")
cap = subprocess.Popen(
    [TSHARK, "-i", "5", "-f", "tcp port 53204", "-w", PCAP],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(1)
print(f"Capture PID: {cap.pid}")

# 3. Open project (triggers fresh auth + Open)
print("Opening project...")
try:
    info = sdk.open_project(PROJECT)
    print(f"Opened: {info.name}")
except Exception as e:
    print(f"Error: {e}")

time.sleep(2)

# 4. Stop capture
cap.terminate()
cap.wait(timeout=5)
print("Capture stopped")

# 5. Extract auth token from capture
r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
if r.stdout.strip():
    payload = bytes.fromhex(r.stdout.strip().split("\t")[-1])
    auth_proto = payload[14:]
    print(f"\nLive auth proto: {len(auth_proto)}B")
    print(f"Hex: {auth_proto.hex()[:200]}")

    # Also check what gRPC calls were made
    r2 = subprocess.run(
        [TSHARK, "-r", PCAP, "-T", "fields", "-e", "frame.number", "-e", "data.data"],
        capture_output=True, text=True
    )
    for line in r2.stdout.splitlines()[:5]:
        if "LSDKMessages" in line or "Open" in line:
            print(f"  {line[:200]}")
else:
    print("No frame 14 — checking for Open frames differently...")
    r3 = subprocess.run(
        [TSHARK, "-r", PCAP, "-T", "fields", "-e", "frame.number", "-e", "tcp.payload"],
        capture_output=True, text=True
    )
    for line in r3.stdout.splitlines()[:10]:
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                d = bytes.fromhex(parts[1])
                if b"Open" in d or b"c0sh" in d:
                    print(f"  Frame {parts[0]}: found Open/c0sh")
            except:
                pass

sdk.close_project()
print("\nDone")
