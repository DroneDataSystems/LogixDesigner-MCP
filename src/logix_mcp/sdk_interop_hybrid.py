"""Hybrid gRPC SDK — SDK for auth/open, gRPC for reads."""
import sys, os, grpc

sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/proto')
import logix_sdk_pb2 as pb
import logix_sdk_pb2_grpc as pb_grpc

from logix_mcp.sdk_interop_real import RealSdkInterop

class HybridSdkInterop(RealSdkInterop):
    """Uses RealSdkInterop for open/close (handles FactoryTalk auth),
    then gRPC for fast read operations (GetAllExecutables, tags, export)."""

    def __init__(self, host: str = "localhost", port: int = 53204):
        super().__init__()
        self._grpc_channel = grpc.insecure_channel(f"{host}:{port}")
        self._grpc_stub = pb_grpc.LogixSDKStub(self._grpc_channel)

    # ── open/close via SDK (handles auth) ────────────────────────────
    # Inherited from RealSdkInterop — no changes needed

    # ── read operations via gRPC ─────────────────────────────────────

    def get_program_structure(self):
        if not self._project:
            raise RuntimeError("No project open")
        try:
            responses = list(self._grpc_stub.GetAllExecutables(pb.EmptyRequest(), timeout=15))
            import re
            programs = {}
            for r in responses:
                for xp in r.executables_result.items:
                    if "/Programs/Program" not in xp or "/Routines/Routine" not in xp:
                        continue
                    pm = re.search(r"Program\[@Name='([^']+)'\]", xp)
                    rm = re.search(r"Routine\[@Name='([^']+)'\]", xp)
                    if pm and rm:
                        programs.setdefault(pm.group(1), []).append(
                            type('RoutineInfo', (), {'name': rm.group(1), 'rung_count': 0, 'language': 'Ladder'})()
                        )
            return [
                type('ProgramInfo', (), {
                    'name': n, 'routine_count': len(rs), 'routines': rs
                })()
                for n, rs in programs.items()
            ]
        except grpc.RpcError as e:
            raise RuntimeError(f"gRPC GetAllExecutables failed: {e.details()}")

    def close(self):
        if self._grpc_channel:
            self._grpc_channel.close()
        super().close_project()


# ── Test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sdk = HybridSdkInterop()
    path = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"
    print(f"Opening {path}...")
    info = sdk.open_project(path)
    print(f"  Controller: {info.name}")

    print("Getting program structure via gRPC...")
    try:
        programs = sdk.get_program_structure()
        for p in programs:
            print(f"  {p.name}: {p.routine_count} routines")
            for r in p.routines[:3]:
                print(f"    - {r.name}")
    except Exception as e:
        print(f"  Error: {e}")

    sdk.close_project()
    sdk.close()
    print("Done")
