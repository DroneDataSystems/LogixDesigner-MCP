"""Test Open by sending actual ACD file data."""
import sys, grpc
sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/proto')

path = r'C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD'
acd_data = open(path, 'rb').read()

c = grpc.insecure_channel('localhost:53204')
raw_stub = c.stream_unary(
    '/LSDKMessages.LogixSDK/Open',
    request_serializer=lambda x: x,
    response_deserializer=lambda x: x
)

# Send file data in field 1
msg = bytes([0x0a, 0xff, 0xff, 0x0f])  # Just try: field 1 with large length prefix
# Actually protobuf can't handle 5MB in one field. Try just the path as field 1
# and the file data as field 2

path_bytes = path.encode()
# Field 1: path, Field 2: file data
import struct
def varint(n):
    buf = []
    while n > 127:
        buf.append((n & 0x7f) | 0x80)
        n >>= 7
    buf.append(n)
    return bytes(buf)

tag1_len = varint(len(path_bytes))
tag2_len = varint(min(len(acd_data), 65536))  # Try first 64KB of file

msg = (bytes([0x0a]) + tag1_len + path_bytes +
       bytes([0x12]) + tag2_len + acd_data[:65536])

try:
    r = raw_stub.future(iter([msg]), timeout=30)
    print(f'RESULT: {r.result()[:500]}')
except grpc.RpcError as e:
    print(f'ERR: {e.code()} — {e.details()[:200]}')

c.close()
