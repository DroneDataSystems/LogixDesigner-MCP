"""Test client-streaming Open gRPC method."""
import sys, grpc
sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/proto')
import logix_sdk_v3_pb2 as pb
import logix_sdk_v3_pb2_grpc as pb_grpc

path = r'C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD'
path_bytes = path.encode()
msg = bytes([0x0a, len(path_bytes)]) + path_bytes

c = grpc.insecure_channel('localhost:53204')

# Try streaming (Open sends file chunks)
stub = pb_grpc.LogixSDKStub(c)

# Try Open as client-streaming using raw stub
raw_stub = c.stream_unary(
    '/LSDKMessages.LogixSDK/Open',
    request_serializer=lambda x: x,
    response_deserializer=lambda x: x
)

# Send path as first chunk, then empty chunk to signal end
try:
    r = raw_stub.future(iter([msg, b'']), timeout=15)
    print(f'STREAM: {r.result()[:300]}')
except grpc.RpcError as e:
    print(f'STREAM ERR: {e.code()} — {e.details()[:150]}')

# Also try sending just one chunk (the path)
try:
    r = raw_stub.future(iter([msg]), timeout=15)
    print(f'SINGLE: {r.result()[:300]}')
except grpc.RpcError as e:
    print(f'SINGLE ERR: {e.code()} — {e.details()[:150]}')

c.close()
