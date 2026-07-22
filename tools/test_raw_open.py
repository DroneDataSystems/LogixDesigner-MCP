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
# The first 8 bytes are metadata prefix (field 1 fixed64=1, field 2 fixed64=6)
# Then field 15 is the auth token
# Let's try with AND without the prefix
auth_no_prefix = auth_raw[8:]
print(f"Auth proto: {len(auth_raw)}B")
print(f"First bytes (with prefix): {auth_raw[:30].hex()}")
print(f"First bytes (no prefix): {auth_no_prefix[:30].hex()}")

# Read ACD
acd = open(ACD, 'rb').read()
print(f"ACD: {len(acd)}B")

# Try both formats
for label, auth in [("with prefix", auth_raw), ("no prefix", auth_no_prefix)]:
    print(f"\n--- Trying {label} ---")
    channel = grpc.insecure_channel('localhost:53204')
    stub = channel.stream_unary(
        '/LSDKMessages.LogixSDK/Open',
        request_serializer=lambda x: x,
        response_deserializer=lambda x: x
    )

    def chunks(a=auth):
        yield a
        chunk_size = 30000
        for i in range(0, len(acd), chunk_size):
            yield acd[i:i+chunk_size]

    try:
        result = stub.future(chunks(), timeout=30)
        print(f"  RESP: {result.result()[:300]}")
    except Exception as e:
        print(f"  ERR: {str(e)[:150]}")
    channel.close()

channel.close()
