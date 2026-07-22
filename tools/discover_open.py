"""Discover the gRPC Open method by trying different protobuf field layouts."""
import sys, grpc
sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/proto')

# Known: /LSDKMessages.LogixSDK/Open exists, needs proper message format
# Error: "Required data chunk not received" — means we need specific fields

def try_open(field_num: int, value: bytes, label: str):
    """Try sending value in a specific protobuf field."""
    # Wire format: (field_num << 3) | 2 (length-delimited), then varint length, then data
    wire_type = 2  # length-delimited (string/bytes)
    tag = (field_num << 3) | wire_type
    msg = bytes([tag, len(value)]) + value

    channel = grpc.insecure_channel('localhost:53204')
    stub = channel.unary_unary(
        '/LSDKMessages.LogixSDK/Open',
        request_serializer=lambda x: x,
        response_deserializer=lambda x: x
    )
    try:
        resp = stub.future(msg, timeout=10).result()
        print(f'  {label}: {resp[:200]}')
    except grpc.RpcError as e:
        print(f'  {label}: {e.code()} — {e.details()[:100]}')
    channel.close()

path = r'C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD'
path_bytes = path.encode('utf-8')

print('=== Testing Open message fields ===')
print(f'Path: {path}')
print(f'Path bytes: {len(path_bytes)}')

# Field 1: project_path
try_open(1, path_bytes, 'Field 1 (project_path)')

# Field 2: maybe project name?
import os
name = os.path.splitext(os.path.basename(path))[0].encode()
try_open(2, name, 'Field 2 (name)')

# Both fields together
msg = (bytes([0x0a, len(path_bytes)]) + path_bytes +
       bytes([0x12, len(name)]) + name)
channel = grpc.insecure_channel('localhost:53204')
stub = channel.unary_unary('/LSDKMessages.LogixSDK/Open',
    request_serializer=lambda x: x, response_deserializer=lambda x: x)
try:
    resp = stub.future(msg, timeout=15).result()
    print(f'  Both fields: {resp[:200]}')
except grpc.RpcError as e:
    print(f'  Both fields: {e.code()} — {e.details()[:100]}')
channel.close()

print('=== Done ===')
