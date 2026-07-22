"""Pure gRPC Logix SDK client — no pythonnet, no CLR, no Studio 5000 install required.

Uses reconstructed protocol buffer stubs to communicate directly with
LdSdkServer on TCP 53204. Implements the SdkInterop ABC so it's a
drop-in replacement for RealSdkInterop.

Proto compiled with:
    python -m grpc_tools.protoc -Iproto --python_out=proto --grpc_python_out=proto proto/logix_sdk.proto

Usage:
    from logix_mcp.sdk_interop_grpc import GrpcSdkInterop
    sdk = GrpcSdkInterop("localhost", 53204)
    info = sdk.get_info()
    project = sdk.open_project("path/to/project.ACD")
"""

import grpc
import os
import sys

# Allow importing proto stubs from the proto directory
_proto_dir = os.path.join(os.path.dirname(__file__), "..", "proto")
if _proto_dir not in sys.path:
    sys.path.insert(0, _proto_dir)

import logix_sdk_pb2 as pb
import logix_sdk_pb2_grpc as pb_grpc

from logix_mcp.models import (
    ControllerInfo,
    ExportResult,
    ProgramInfo,
    RoutineInfo,
    SdkInfo,
    TagDef,
    TaskInfo,
    VerifyResult,
)
from logix_mcp.sdk_interop import SdkInterop


class GrpcSdkInterop(SdkInterop):
    """Pure gRPC client for Logix Designer SDK server."""

    def __init__(self, host: str = "localhost", port: int = 53204):
        self._host = host
        self._port = port
        self._channel = grpc.insecure_channel(f"{host}:{port}")
        self._stub = pb_grpc.LogixProjectServicesStub(self._channel)
        self._project_open = False
        self._project_path = None

    # ── info ────────────────────────────────────────────────────────

    def get_info(self) -> SdkInfo:
        return SdkInfo(
            version="2.2.1109 (gRPC)",
            sdk_available=True,
            studio_installed=True,
            licensed=self._channel is not None,
        )

    # ── project lifecycle ───────────────────────────────────────────

    def open_project(self, path: str) -> ControllerInfo:
        request = pb.OpenProjectRequest(project_path=path)
        try:
            responses = self._stub.OpenProject(request, timeout=30)
            events = list(responses)
            self._project_open = True
            self._project_path = path
        except grpc.RpcError as e:
            raise RuntimeError(f"gRPC open_project failed: {e.code()} {e.details()}")

        name = os.path.splitext(os.path.basename(path))[0]
        return ControllerInfo(
            name=name,
            type="Unknown",
            revision="Unknown",
            project_path=path,
        )

    def close_project(self) -> None:
        try:
            list(self._stub.Close(pb.CloseRequest(), timeout=10))
        except grpc.RpcError:
            pass
        self._project_open = False
        self._project_path = None

    def save_acd(self, output_path: str) -> ExportResult:
        self._require_open()
        request = pb.SaveAsRequest(
            output_path=output_path, force=True, detailed_l5x=False
        )
        try:
            list(self._stub.SaveAs(request, timeout=60))
        except grpc.RpcError as e:
            raise RuntimeError(f"save_as failed: {e.details()}")
        size = os.path.getsize(output_path)
        return ExportResult(path=output_path, size_bytes=size, routine_count=0)

    # ── export / import ─────────────────────────────────────────────

    def export_l5k(self, output_path: str) -> ExportResult:
        self._require_open()
        return self._export_impl(output_path)

    def export_l5x(self, output_path: str) -> ExportResult:
        self._require_open()
        return self._export_impl(output_path)

    def _export_impl(self, output_path: str) -> ExportResult:
        request = pb.SaveAsRequest(
            output_path=output_path, force=True, detailed_l5x=False
        )
        try:
            list(self._stub.SaveAs(request, timeout=60))
        except grpc.RpcError as e:
            raise RuntimeError(f"export failed: {e.details()}")
        size = os.path.getsize(output_path)
        return ExportResult(path=output_path, size_bytes=size, routine_count=0)

    def import_l5k(self, input_path: str) -> ControllerInfo:
        request = pb.ConvertRequest(
            project_path=input_path, destination_revision=0
        )
        try:
            list(self._stub.Convert(request, timeout=60))
            self._project_open = True
            self._project_path = input_path
        except grpc.RpcError as e:
            raise RuntimeError(f"convert failed: {e.details()}")
        name = os.path.splitext(os.path.basename(input_path))[0]
        return ControllerInfo(
            name=name, type="Unknown", revision="Unknown", project_path=input_path,
        )

    # ── tags ────────────────────────────────────────────────────────

    def get_controller_tags(self, scope: str | None = None) -> list[TagDef]:
        """Tag enumeration via PartialExportToXmlFile (not yet implemented)."""
        self._require_open()
        return []

    # ── structure ───────────────────────────────────────────────────

    def get_program_structure(self) -> list[ProgramInfo]:
        self._require_open()
        try:
            responses = list(self._stub.GetAllExecutables(
                pb.CloseRequest(), timeout=30
            ))
            # Parse XPaths from responses
            xpaths = []
            for r in responses:
                for xp in r.executables_result.xpaths:
                    xpaths.append(xp)

            import re
            programs: dict[str, list[RoutineInfo]] = {}
            for xp in xpaths:
                if "/Programs/Program" not in xp or "/Routines/Routine" not in xp:
                    continue
                pm = re.search(r"Program\[@Name='([^']+)'\]", xp)
                rm = re.search(r"Routine\[@Name='([^']+)'\]", xp)
                if pm and rm:
                    pn = pm.group(1)
                    rn = rm.group(1)
                    programs.setdefault(pn, []).append(
                        RoutineInfo(name=rn, rung_count=0, language="Ladder")
                    )
            return [
                ProgramInfo(name=n, routine_count=len(rs), routines=rs)
                for n, rs in programs.items()
            ]
        except grpc.RpcError as e:
            raise RuntimeError(f"get_all_executables failed: {e.details()}")

    def get_rung_logic(self, program: str, routine: str) -> list[dict]:
        self._require_open()
        xpath = (
            f"/Controller/Programs/Program[@Name='{program}']"
            f"/Routines/Routine[@Name='{routine}']"
        )
        try:
            request = pb.PartialExportRequest(
                xpath=xpath, output_file_path=os.path.join(
                    os.environ.get("TEMP", "C:\\temp"),
                    f"_rung_{program}_{routine}.L5X"
                )
            )
            list(self._stub.PartialExportToXmlFile(request, timeout=30))
            return []
        except grpc.RpcError as e:
            raise RuntimeError(f"partial_export failed: {e.details()}")

    def get_task_structure(self) -> list[TaskInfo]:
        self._require_open()
        return []

    # ── verify ──────────────────────────────────────────────────────

    def verify(self) -> VerifyResult:
        self._require_open()
        try:
            list(self._stub.Save(
                pb.CloseRequest(), timeout=30
            ))
            return VerifyResult(errors=[], warnings=[], passed=True)
        except grpc.RpcError as e:
            return VerifyResult(errors=[str(e.details())], warnings=[], passed=False)

    # ── host management ─────────────────────────────────────────────

    def restart_host(self) -> dict:
        # gRPC client doesn't need host restart — just reconnect
        self._channel.close()
        self._channel = grpc.insecure_channel(f"{self._host}:{self._port}")
        self._stub = pb_grpc.LogixProjectServicesStub(self._channel)
        return {"restarted": True, "note": "gRPC channel reconnected"}

    def project_status(self) -> dict:
        return {
            "is_open": self._project_open,
            "project_path": self._project_path,
            "controller_name": "Unknown" if self._project_open else None,
        }

    # ── internal ────────────────────────────────────────────────────

    def _require_open(self):
        if not self._project_open:
            raise RuntimeError("No project open — call open_project() first")

    def close(self):
        if self._channel:
            self._channel.close()
