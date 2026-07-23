"""Complete gRPC flow: capture auth → Open → GetAllExecutables → ExportToL5K → parse."""
import sys, grpc, subprocess, time, zlib

sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/proto')
import logix_sdk_pb2 as pb
import logix_sdk_pb2_grpc as pb_grpc

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"
SERVICE = "LogixMCPServer"
PCAP = r"C:\temp\grpc_flow.pcapng"

# ── Phase 1: Capture fresh auth token ──────────────────────────────────
print("=== Phase 1: Capture auth token ===")
cap = subprocess.Popen([TSHARK, "-i", "5", "-f", "tcp port 53204", "-w", PCAP],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(1)
subprocess.run(["sc", "stop", SERVICE], capture_output=True, timeout=30)
time.sleep(5)
subprocess.run(["sc", "start", SERVICE], capture_output=True, timeout=30)
time.sleep(12)

sys.path.insert(0, r"C:\projects\LogixDesigner-MCP\src")
from logix_mcp.sdk_interop_real import RealSdkInterop
sdk = RealSdkInterop()
sdk.open_project(ACD)
time.sleep(2)
sdk.close_project()
cap.terminate(); cap.wait(timeout=5)

# Extract token
r = subprocess.run([TSHARK, "-r", PCAP, "-Y", "tcp.payload", "-T", "fields", "-e", "tcp.payload"],
                   capture_output=True, text=True)
auth_token = None
for line in r.stdout.splitlines()[:200]:
    parts = line.split("\t")
    if len(parts) < 2: continue
    try:
        d = bytes.fromhex(parts[1])
        idx = d.find(b'c0sh')
        if idx < 14: continue
        tag_pos = idx
        while tag_pos > 0 and d[tag_pos] != 0x0a: tag_pos -= 1
        if tag_pos == 0: continue
        length = 0; shift = 0; p = tag_pos + 1
        while p < len(d):
            b = d[p]; p += 1
            length |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        token = d[p:p+length]
        if len(token) >= 1500: auth_token = token; break
    except: pass

if not auth_token: print("FAILED"); sys.exit(1)
print(f"Token: {len(auth_token)}B\n")

# ── Phase 2: gRPC Open ─────────────────────────────────────────────────
print("=== Phase 2: gRPC Open ===")
acd_data = open(ACD, 'rb').read()
crc = zlib.crc32(acd_data) & 0xFFFFFFFF
channel = grpc.insecure_channel('localhost:53204')
stub = pb_grpc.LogixSDKStub(channel)

def open_chunks():
    m = pb.ProjectOpenRequest(); m.user_token = auth_token.decode('latin-1'); yield m
    for i in range(0, len(acd_data), 30000):
        m2 = pb.ProjectOpenRequest(); m2.file_data.content = acd_data[i:i+30000]; yield m2
    m3 = pb.ProjectOpenRequest(); m3.file_data.crc32 = crc; yield m3

responses = list(stub.Open(open_chunks(), timeout=60))
project_key = None
for r in responses:
    if r.HasField('data') and r.data.HasField('string_value'):
        project_key = r.data.string_value
print(f"  ProjectKey: {project_key}")

# ── Phase 3: GetAllExecutables ─────────────────────────────────────────
print("\n=== Phase 3: GetAllExecutables ===")
req = pb.ProjectRequest(key=project_key)
responses = list(stub.GetAllExecutables(req, timeout=15))
for r in responses:
    if r.HasField('data') and r.data.HasField('string_array_value'):
        xpaths = r.data.string_array_value.values
        print(f"  {len(xpaths)} executables:")
        for xp in xpaths[:10]:
            print(f"    {xp}")

# ── Phase 4: ExportToL5K ──────────────────────────────────────────────
print("\n=== Phase 4: ExportToL5K ===")
out = r"C:\temp\grpc_export.L5K"
req2 = pb.ProjectRequest(key=project_key)
responses = list(stub.ExportToL5K(req2, timeout=30))
export_data = b""
for r in responses:
    if r.HasField('data') and r.data.HasField('string_value'):
        export_data += r.data.string_value.encode('utf-8')

with open(out, 'wb') as f: f.write(export_data)
print(f"  Exported {len(export_data)}B")

# ── Phase 5: Parse with L5K parser ────────────────────────────────────
print("\n=== Phase 5: L5K Parse ===")
from plc_parser.l5k import parse_l5k
ctrl = parse_l5k(out)
print(f"  Controller: {ctrl.name} v{ctrl.major}.{ctrl.minor}")
print(f"  Processor: {ctrl.processor_type}")
print(f"  Tags: {len(ctrl.tags)}, Programs: {len(ctrl.programs)}")
total_routines = sum(len(p.routines) for p in ctrl.programs)
print(f"  Total routines: {total_routines}")

channel.close()
print("\n=== FULL FLOW COMPLETE ===")
