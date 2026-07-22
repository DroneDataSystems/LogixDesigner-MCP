"""Send raw bytes via TCP — bypass gRPC library entirely."""
import subprocess, socket, struct, time

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_live_auth.pcapng"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"

# Extract exact auth message
r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
payload = bytes.fromhex(r.stdout.strip().split("\t")[-1])
auth_msg = payload[9:]  # HTTP/2 DATA after 9-byte frame header = gRPC frame + message
print(f"Auth gRPC frame: {len(auth_msg)}B")
print(f"  Compression: {auth_msg[0]}, Length: {int.from_bytes(auth_msg[1:5], 'big')}")

acd = open(ACD, 'rb').read()
print(f"ACD: {len(acd)}B")

# Build the complete gRPC data stream (all frames concatenated)
# gRPC frame format: [1B compression][4B length big-endian][message bytes]
def grpc_frame(data):
    length = len(data)
    hdr = bytes([0, (length >> 24) & 0xff, (length >> 16) & 0xff, (length >> 8) & 0xff, length & 0xff])
    return hdr + data

proto_auth = auth_msg[5:]  # skip gRPC frame header (5B) = raw protobuf
print(f"Proto auth: {len(proto_auth)}B")

# Build entire stream payload
full_stream = grpc_frame(proto_auth)
for i in range(0, len(acd), 30000):
    chunk = acd[i:i+30000]
    # Wrap in protobuf field 2
    length = len(chunk)
    varint = []
    l = length
    while l > 127:
        varint.append((l & 0x7f) | 0x80)
        l >>= 7
    varint.append(l)
    wrapped = bytes([0x12]) + bytes(varint) + chunk
    full_stream += grpc_frame(wrapped)

print(f"Total stream: {len(full_stream)}B")

# Connect raw TCP — send HTTP/2 preface + headers + data
# This is getting complex. Let me try a different approach:
# Use the SDK's OWN gRPC channel!

# Actually, let me check if the SDK has an open connection we can piggyback on
# The LogixMCPServer is running and already has an authenticated connection.
# We can just call GetAllExecutables on the same channel.

# Or... let me try calling Open through the MCP tool (which works) and then
# using gRPC to call GetAllExecutables on the same connection.

# Simplest test: call GetAllExecutables while project is open via SDK
print("\n--- Calling GetAllExecutables via gRPC (SDK has project open) ---")
sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/proto')
import grpc, sys
import logix_sdk_pb2 as pb
import logix_sdk_pb2_grpc as pb_grpc

channel = grpc.insecure_channel('localhost:53204')
stub = pb_grpc.LogixSDKStub(channel)

try:
    responses = list(stub.GetAllExecutables(pb.EmptyRequest(), timeout=10))
    for r in responses:
        result = r.WhichOneof('result')
        if result:
            val = getattr(r, result)
            print(f"  {result}: {str(val)[:200]}")
except grpc.RpcError as e:
    print(f"  gRPC error: {e.code()} — {e.details()}")

channel.close()
