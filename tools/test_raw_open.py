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
auth_msg = payload[14:]  # Entire gRPC message including 5-byte header
print(f"Auth message: {len(auth_msg)}B")
print(f"Auth header: compression={auth_msg[0]}, length={int.from_bytes(auth_msg[1:5], 'big')}")

# Read ACD
acd = open(ACD, 'rb').read()
print(f"ACD: {len(acd)}B")

# Build raw gRPC stream
channel = grpc.insecure_channel('localhost:53204')
stub = channel.stream_unary(
    '/LSDKMessages.LogixSDK/Open',
    request_serializer=lambda x: x,
    response_deserializer=lambda x: x
)

def chunks():
    yield auth_msg  # message 1: auth (with gRPC header)
    chunk_size = 30000
    for i in range(0, len(acd), chunk_size):
        data = acd[i:i+chunk_size]
        hdr = bytes([
            0,
            (len(data) >> 24) & 0xff,
            (len(data) >> 16) & 0xff,
            (len(data) >> 8) & 0xff,
            len(data) & 0xff
        ])
        yield hdr + data

print("Sending...")
try:
    result = stub.future(chunks(), timeout=30)
    print(f"RESP: {result.result()[:500]}")
except Exception as e:
    print(f"ERR: {str(e)[:200]}")

channel.close()
