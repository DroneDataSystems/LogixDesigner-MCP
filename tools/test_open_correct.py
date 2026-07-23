"""Test gRPC Open with correct proto from decompiled C# source."""
import sys, grpc, subprocess, time, struct, zlib

sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/proto')
import logix_sdk_pb2 as pb
import logix_sdk_pb2_grpc as pb_grpc

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"
SERVICE = "LogixMCPServer"

# ── Step 1: Start capture FIRST, then restart service ──────────────────
print("Starting capture...")
PCAP = r"C:\temp\grpc_live_test.pcapng"
cap = subprocess.Popen(
    [TSHARK, "-i", "5", "-f", "tcp port 53204", "-w", PCAP],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(1)

print("Restarting service...")
subprocess.run(["sc", "stop", SERVICE], capture_output=True, timeout=30)
time.sleep(5)
subprocess.run(["sc", "start", SERVICE], capture_output=True, timeout=30)
time.sleep(10)  # Wait for SDK init + auth handshake

# Open project via SDK to generate fresh auth
print("Opening project via SDK...")
sys.path.insert(0, r"C:\projects\LogixDesigner-MCP\src")
from logix_mcp.sdk_interop_real import RealSdkInterop
sdk = RealSdkInterop()
try:
    info = sdk.open_project(ACD)
    print(f"  Opened: {info.name}")
except Exception as e:
    print(f"  Error: {e}")
time.sleep(2)
sdk.close_project()

# Stop capture
cap.terminate()
cap.wait(timeout=5)
print("Capture stopped")

# ── Step 2: Extract auth token ─────────────────────────────────────────
r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "tcp.payload", "-T", "fields",
     "-e", "frame.number", "-e", "tcp.payload"],
    capture_output=True, text=True
)

auth_token = None
lines = r.stdout.splitlines()
print(f"  Scanning {len(lines)} payload frames...")
for line in lines[:200]:  # Only need first 200 frames
    parts = line.split("\t")
    if len(parts) >= 2:
        try:
            d = bytes.fromhex(parts[1])
            # Look for the auth token: starts with "c0sh" after HTTP/2+gRPC headers
            idx = d.find(b'c0sh')
            if idx > 20:  # After headers
                # Extract the full base64 token (1656 bytes)
                proto_data = d[idx-2:]  # -2 for the field tag + length varint
                # The auth message: field 1 tag (0x0a) + varint length (2 bytes) + token (1656 bytes)
                # Extract just the token string
                if proto_data[0] == 0x0a:  # field 1 tag
                    # Read varint length
                    length = 0; shift = 0; pos = 1
                    while pos < len(proto_data):
                        b = proto_data[pos]; pos += 1
                        length |= (b & 0x7f) << shift
                        if not (b & 0x80): break
                        shift += 7
                    token = proto_data[pos:pos+length]
                    if len(token) >= 1500 and b'c0sh' in token[:10]:
                        auth_token = token
                        print(f"  Auth token: {len(auth_token)}B")
                        break
        except:
            pass

if not auth_token:
    print("FAILED: Could not extract auth token")
    sys.exit(1)

# ── Step 3: gRPC Open with correct proto ───────────────────────────────
print("\n=== gRPC Open ===")
acd_data = open(ACD, 'rb').read()
print(f"ACD: {len(acd_data)}B")

channel = grpc.insecure_channel('localhost:53204')
stub = pb_grpc.LogixSDKStub(channel)

# Compute CRC32 of the ACD file
crc = zlib.crc32(acd_data) & 0xFFFFFFFF

def request_stream():
    # Message 1: user_token
    msg1 = pb.ProjectOpenRequest()
    msg1.user_token = auth_token.decode('latin-1')
    yield msg1

    # Messages 2-N: file_data.content
    chunk_size = 30000
    for i in range(0, len(acd_data), chunk_size):
        msg = pb.ProjectOpenRequest()
        msg.file_data.content = acd_data[i:i+chunk_size]
        yield msg

    # Final message: file_data.crc32
    msg_final = pb.ProjectOpenRequest()
    msg_final.file_data.crc32 = crc
    yield msg_final

print(f"Sending {len(acd_data)//30000 + 2} messages (CRC32=0x{crc:08x})...")
try:
    responses = list(stub.Open(request_stream(), timeout=60))
    for r in responses:
        result = r.WhichOneof('result')
        if result == 'operation_result':
            op = r.operation_result
            print(f"  Result: {op.result_value} — {op.result_message[:200]}")
        elif result == 'data':
            d = r.data
            dv = d.WhichOneof('value')
            if dv:
                print(f"  Data.{dv}: {getattr(d, dv)}")
    print("SUCCESS!")
except grpc.RpcError as e:
    print(f"  gRPC Error: {e.code()} — {e.details()[:200]}")

channel.close()
