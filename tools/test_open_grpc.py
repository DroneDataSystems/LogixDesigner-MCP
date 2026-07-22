"""Test gRPC Open with captured FactoryTalk auth token."""
import sys, grpc, subprocess

sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/proto')
import logix_sdk_pb2 as pb
import logix_sdk_pb2_grpc as pb_grpc

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_open_decode.pcapng"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"

# ── Extract auth token from capture ───────────────────────────────────
print("Extracting auth token from capture...")
r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
data = bytes.fromhex(r.stdout.strip().split("\t")[-1])
proto = data[14:]  # HTTP/2 (9B) + gRPC (5B)
auth_token = proto[3:3+1656]  # field 1 tag(1B) + varint_len(2B) + value(1656B)
print(f"  Auth token: {len(auth_token)}B, starts: {auth_token[:30]}")

# ── Read ACD file ─────────────────────────────────────────────────────
acd_data = open(ACD, 'rb').read()
print(f"  ACD: {len(acd_data)}B")

# ── gRPC client-streaming Open ────────────────────────────────────────
channel = grpc.insecure_channel('localhost:53204')
stub = pb_grpc.LogixSDKStub(channel)

# Build the streaming request
def request_iterator():
    # Message 1: auth token
    chunk1 = pb.FileChunk()
    chunk1.auth_token = auth_token
    yield chunk1

    # Messages 2-N: file data in 30KB chunks
    chunk_size = 30000
    for i in range(0, len(acd_data), chunk_size):
        chunk = pb.FileChunk()
        chunk.file_data = acd_data[i:i+chunk_size]
        yield chunk

print("Sending Open request...")
try:
    responses = list(stub.Open(request_iterator(), timeout=30))
    for i, r in enumerate(responses):
        result = r.WhichOneof('result')
        if result:
            val = getattr(r, result)
            print(f"  Response {i}: {result} = {str(val)[:200]}")
        else:
            print(f"  Response {i}: <empty>")
    print("SUCCESS!")
except grpc.RpcError as e:
    print(f"  gRPC Error: {e.code()} — {e.details()[:200]}")

channel.close()
