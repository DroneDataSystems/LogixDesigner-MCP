"""Capture and decode the gRPC Open request to extract protobuf fields.

Strategy:
1. Restart LogixMCPServer (kills stale connections)
2. Start tshark capture on loopback port 53204
3. Open a project via SDK (triggers fresh Open gRPC call)
4. Stop capture and extract the Open request protobuf body
5. Decode field numbers and types
"""
import subprocess, time, os, sys, re, struct

# ── Config ───────────────────────────────────────────────────────────
PROJECT = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"
PCAP_PATH = r"C:\temp\grpc_open_decode.pcapng"
TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
SERVICE = "LogixMCPServer"
VENV_PYTHON = r"C:\projects\LogixDesigner-MCP\.venv\Scripts\python.exe"
TOOLS_DIR = r"C:\projects\LogixDesigner-MCP\tools"

# ── Step 1: Restart the service ──────────────────────────────────────
print("=== Step 1: Restarting LogixMCPServer ===")
subprocess.run(["sc", "stop", SERVICE], capture_output=True, timeout=30)
time.sleep(3)
subprocess.run(["sc", "start", SERVICE], capture_output=True, timeout=30)
print("  Service restart initiated")
time.sleep(8)  # Let FastMCP start up and connect to LdSdkServer

# ── Step 2: Start capture ────────────────────────────────────────────
print("=== Step 2: Starting capture ===")
cap = subprocess.Popen(
    [TSHARK, "-i", "5", "-f", "tcp port 53204", "-w", PCAP_PATH],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(1)
print(f"  Capture PID: {cap.pid}")

# ── Step 3: Open project via SDK directly ──────────────────────────────
print("=== Step 3: Opening project ===")
sys.path.insert(0, r"C:\projects\LogixDesigner-MCP\src")
from logix_mcp.sdk_interop_real import RealSdkInterop
try:
    sdk = RealSdkInterop()
    info = sdk.open_project(PROJECT)
    print(f"  Opened: {info}")
    sdk.close_project()
except Exception as e:
    print(f"  Error: {e}")

time.sleep(2)

# ── Step 4: Stop capture ─────────────────────────────────────────────
print("=== Step 4: Stopping capture ===")
cap.terminate()
cap.wait(timeout=5)
print("  Capture stopped")

# ── Step 5: Extract Open request protobuf ─────────────────────────────
print("=== Step 5: Extracting Open request protobuf ===")
# Use tshark to find frames with data and search for the Open pattern
result = subprocess.run(
    [TSHARK, "-r", PCAP_PATH, "-Y", "data", "-T", "fields",
     "-e", "frame.number", "-e", "data.data"],
    capture_output=True, text=True, timeout=15
)

open_frame_data = []
for line in result.stdout.splitlines():
    if "4c53444b4d657373616765732e4c6f67697853444b2f4f70656e" in line:  # LSDKMessages.LogixSDK/Open hex
        parts = line.split("\t")
        print(f"  Found Open in frame {parts[0]}")
        open_frame_data.append(parts)

# ── Step 6: Decode protobuf ──────────────────────────────────────────
if open_frame_data:
    print("\n=== Step 6: Protobuf field analysis ===")
    # Get the data bytes from the Open frame
    # The gRPC data frame is right after the headers frame
    # Let's try to get the data from the next frame after the headers
    frame_num = int(open_frame_data[0][0])
    # Get the data from the next few frames
    for delta in range(1, 5):
        result2 = subprocess.run(
            [TSHARK, "-r", PCAP_PATH, "-Y", f"frame.number == {frame_num + delta}",
             "-T", "fields", "-e", "data.data"],
            capture_output=True, text=True, timeout=10
        )
        if result2.stdout.strip():
            hexdata = result2.stdout.strip().split("\t")[-1]
            try:
                raw = bytes.fromhex(hexdata)
                # Skip gRPC frame header (5 bytes)
                if len(raw) > 5:
                    proto_data = raw[5:]
                    print(f"\n  Frame {frame_num + delta}: {len(proto_data)} bytes")
                    print(f"  Raw hex: {proto_data.hex()[:200]}")
                    # Try to parse protobuf fields
                    parse_protobuf(proto_data)
                    break  # Only need the first data frame
            except Exception as e:
                print(f"  Decode error: {e}")
else:
    print("\n  Could not find Open frame. Dumping all gRPC calls:")
    for line in result.stdout.splitlines()[:20]:
        print(f"  {line[:200]}")

def parse_protobuf(data: bytes):
    """Naive protobuf field parser."""
    pos = 0
    while pos < len(data):
        if pos >= len(data):
            break
        # Read tag
        tag = data[pos]
        field_num = tag >> 3
        wire_type = tag & 0x07
        pos += 1

        wire_names = {0: "varint", 1: "fixed64", 2: "length-delimited", 5: "fixed32"}

        if wire_type == 0:  # varint
            value = 0
            shift = 0
            while pos < len(data):
                b = data[pos]
                pos += 1
                value |= (b & 0x7f) << shift
                if not (b & 0x80):
                    break
                shift += 7
            print(f"  Field {field_num} (varint): {value}")
        elif wire_type == 2:  # length-delimited
            # Read length varint
            length = 0
            shift = 0
            while pos < len(data):
                b = data[pos]
                pos += 1
                length |= (b & 0x7f) << shift
                if not (b & 0x80):
                    break
                shift += 7
            value = data[pos:pos+length]
            pos += length
            # Try to decode as string
            try:
                text = value.decode('utf-8')
                if len(text) < 200:
                    print(f"  Field {field_num} (string, {length}B): {text}")
                else:
                    print(f"  Field {field_num} (bytes, {length}B)")
            except:
                print(f"  Field {field_num} (bytes, {length}B): {value.hex()[:50]}...")
        else:
            print(f"  Field {field_num} ({wire_names.get(wire_type, str(wire_type))}) — skipping")
            break  # Don't know how to skip

print("\n=== Done ===")
