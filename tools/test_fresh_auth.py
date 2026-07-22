"""Test gRPC Open with FRESH live auth token."""
import subprocess, grpc

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_live_auth.pcapng"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"

# Extract fresh auth
r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
payload = bytes.fromhex(r.stdout.strip().split("\t")[-1])
auth_proto = payload[14:]
print(f"Auth: {len(auth_proto)}B, start: {auth_proto[:40].hex()}")

# Read ACD
acd = open(ACD, 'rb').read()
print(f"ACD: {len(acd)}B")

# Send
channel = grpc.insecure_channel('localhost:53204')
stub = channel.stream_unary(
    '/LSDKMessages.LogixSDK/Open',
    request_serializer=lambda x: x,
    response_deserializer=lambda x: x
)

def chunks():
    yield auth_proto
    sz = 30000
    for i in range(0, len(acd), sz):
        yield acd[i:i+sz]

try:
    result = stub.future(chunks(), timeout=30)
    resp = result.result()
    print(f"RESP ({len(resp)}B): {resp[:500]}")
    # Try to decode OperationResponse
    if resp:
        pos = 0
        while pos < len(resp) and pos < 100:
            tag = resp[pos]; pos += 1
            fn = tag >> 3; wt = tag & 7
            if wt == 2:
                length = 0; shift = 0
                while pos < len(resp):
                    b = resp[pos]; pos += 1
                    length |= (b & 0x7f) << shift
                    if not (b & 0x80): break
                    shift += 7
                val = resp[pos:pos+length]; pos += length
                try:
                    print(f"  Field {fn}: {val.decode('utf-8', errors='replace')[:200]}")
                except:
                    print(f"  Field {fn}: {val[:100].hex()}")
except Exception as e:
    print(f"ERR: {e}")

channel.close()
