"""Test raw gRPC Open with exact bytes from capture."""
import subprocess, grpc

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_open_decode.pcapng"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"

# Extract the exact auth message from capture
r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
payload = bytes.fromhex(r.stdout.strip().split("\t")[-1])
auth_raw = payload[14:]  # skip HTTP/2 (9B) + gRPC frame (5B) = raw protobuf
print(f"Auth proto: {len(auth_raw)}B")
print(f"First bytes: {auth_raw[:20].hex()}")

# Read ACD
acd = open(ACD, 'rb').read()
print(f"ACD: {len(acd)}B")

# Build raw gRPC stream — library handles gRPC framing
channel = grpc.insecure_channel('localhost:53204')
stub = channel.stream_unary(
    '/LSDKMessages.LogixSDK/Open',
    request_serializer=lambda x: x,
    response_deserializer=lambda x: x
)

def chunks():
    yield auth_raw  # message 1: raw protobuf (auth token)
    chunk_size = 30000
    for i in range(0, len(acd), chunk_size):
        yield acd[i:i+chunk_size]

print("Sending...")
try:
    result = stub.future(chunks(), timeout=30)
    print(f"RESP: {result.result()[:500]}")
except Exception as e:
    print(f"ERR: {str(e)[:200]}")

channel.close()
