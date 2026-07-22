"""Test with protobuf-wrapped file chunks."""
import subprocess, grpc

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_live_auth.pcapng"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
payload = bytes.fromhex(r.stdout.strip().split("\t")[-1])
auth_proto = payload[14:]
print(f"Auth proto: {len(auth_proto)}B, start: {auth_proto[:30].hex()}")

acd = open(ACD, 'rb').read()
print(f"ACD: {len(acd)}B")

# Helper to encode protobuf field 2 length-delimited
def proto_field2(data):
    """Wrap data in protobuf field 2 (tag 0x12) with length-delimited wire type."""
    length = len(data)
    # Encode varint length
    varint = []
    while length > 127:
        varint.append((length & 0x7f) | 0x80)
        length >>= 7
    varint.append(length)
    return bytes([0x12]) + bytes(varint) + data

channel = grpc.insecure_channel('localhost:53204')
stub = channel.stream_unary(
    '/LSDKMessages.LogixSDK/Open',
    request_serializer=lambda x: x,
    response_deserializer=lambda x: x
)

def chunks():
    yield auth_proto  # message 1: field 1 = auth token (raw protobuf)
    for i in range(0, len(acd), 30000):
        chunk = acd[i:i+30000]
        yield proto_field2(chunk)  # message 2+: field 2 = file data (wrapped)

try:
    result = stub.future(chunks(), timeout=30)
    print(f"\nRESP: {result.result()[:500]}")
except Exception as e:
    print(f"\nERR: {e}")
channel.close()
