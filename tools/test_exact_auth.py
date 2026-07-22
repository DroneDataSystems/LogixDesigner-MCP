"""Test with OUTER envelope prefix included."""
import subprocess, grpc

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\temp\grpc_live_auth.pcapng"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"

r = subprocess.run(
    [TSHARK, "-r", PCAP, "-Y", "frame.number==14", "-T", "fields", "-e", "tcp.payload"],
    capture_output=True, text=True
)
payload = bytes.fromhex(r.stdout.strip().split("\t")[-1])
# Take the EXACT bytes from capture (including the prefix)
auth_full = payload[14:]  # 1659 bytes total

# But wait — let's also check the ENTIRE gRPC frame including the 5-byte header
# to see if there's a different message boundary
print(f"Full auth payload (after HTTP/2): {len(auth_full)}B")
print(f"Bytes 0-20: {auth_full[:20].hex()}")
print(f"Bytes 0-8 (prefix): {auth_full[:8].hex()}")
print(f"Bytes 8-20 (group + token): {auth_full[8:20].hex()}")

# New theory: the message has:
# Outer 8 bytes: fixed32 field1=1, fixed32 field2=6 (envelope)
# Then: field 15 (group) containing field 1 (string) with the auth token
# The group wrapping means we need to send 0x7b (start group 15) + 0x0a (field 1 string) + token + 0x7c (end group 15)

# Let me try sending the EXACT full message as captured
acd = open(ACD, 'rb').read()

channel = grpc.insecure_channel('localhost:53204')
stub = channel.stream_unary(
    '/LSDKMessages.LogixSDK/Open',
    request_serializer=lambda x: x,
    response_deserializer=lambda x: x
)

def chunks():
    yield auth_full  # exact bytes from capture
    for i in range(0, len(acd), 30000):
        yield acd[i:i+30000]

try:
    result = stub.future(chunks(), timeout=30)
    print(f"\nRESP: {result.result()[:500]}")
except Exception as e:
    print(f"\nERR: {e}")
channel.close()
