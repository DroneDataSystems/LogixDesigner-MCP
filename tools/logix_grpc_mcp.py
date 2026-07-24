"""Hermes MCP server for Logix gRPC — runs on Linux, tunnels to Windows SDK.

Provides tools for opening ACDs, exporting L5K/L5X, and listing executables
through the Cloudflare TCP tunnel to LdSdkServer on Windows.

Auth token is read from ~/.hermes/grpc_auth_token.bin (maintained by cron job).
"""
import asyncio
import json
import os
import signal
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import grpc

# Proto stubs compiled into same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logix_sdk_pb2 as pb
import logix_sdk_pb2_grpc as pb_grpc

TUNNEL_HOST = "grpc-mcp.jbray.net"
TUNNEL_PORT = 55321
GRPC_PORT = 55321  # local tunnel endpoint
TOKEN_PATH = os.path.expanduser("~/.hermes/grpc_auth_token.bin")
CHUNK_SIZE = 30000

# Track open projects
_active_projects: dict[str, str] = {}  # project_key -> acd_name
_tunnel_process: subprocess.Popen | None = None


def ensure_tunnel():
    """Ensure the Cloudflare TCP tunnel is running."""
    global _tunnel_process
    if _tunnel_process is not None and _tunnel_process.poll() is None:
        return  # Already running

    cmd = [
        "cloudflared", "access", "tcp",
        "--hostname", TUNNEL_HOST,
        "--url", f"127.0.0.1:{TUNNEL_PORT}",
    ]
    _tunnel_process = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(3)  # Let it establish


def get_token() -> bytes:
    """Read cached auth token."""
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(f"No token at {TOKEN_PATH}")
    return Path(TOKEN_PATH).read_bytes()


def grpc_stub():
    """Create a gRPC stub through the tunnel."""
    channel = grpc.insecure_channel(f"localhost:{GRPC_PORT}")
    return pb_grpc.LogixSDKStub(channel)


# ═══════════════════════════════════════════════════════════════════════
# MCP Tools
# ═══════════════════════════════════════════════════════════════════════

def open_project_grpc(acd_path: str) -> dict:
    """Open an ACD file on the Windows machine via gRPC.

    Args:
        acd_path: Full path to ACD file on the WINDOWS machine
                  (e.g., C:\\Users\\...\\Mativ_Sim.ACD)

    Returns:
        Project key (UUID string) for use with other tools,
        or error message if opening failed.
    """
    ensure_tunnel()
    try:
        token = get_token()
        acd_data = open(acd_path, "rb").read()
        crc = zlib.crc32(acd_data) & 0xFFFFFFFF
    except FileNotFoundError as e:
        return {"error": str(e)}

    stub = grpc_stub()

    def chunks():
        m = pb.ProjectOpenRequest()
        m.user_token = token.decode("latin-1")
        yield m
        for i in range(0, len(acd_data), CHUNK_SIZE):
            m2 = pb.ProjectOpenRequest()
            m2.file_data.content = acd_data[i : i + CHUNK_SIZE]
            yield m2
        m3 = pb.ProjectOpenRequest()
        m3.file_data.crc32 = crc
        yield m3

    try:
        responses = list(stub.Open(chunks(), timeout=90))
    except grpc.RpcError as e:
        return {"error": f"gRPC error: {e.code()} — {e.details()[:200]}"}

    project_key = None
    error_msg = None
    for r in responses:
        if r.HasField("data") and r.data.HasField("string_value"):
            project_key = r.data.string_value
        elif r.HasField("operation_result"):
            op = r.operation_result
            if op.result_value != 0:
                error_msg = op.result_message

    if project_key:
        name = os.path.basename(acd_path)
        _active_projects[project_key] = name
        return {
            "project_key": project_key,
            "file": name,
            "status": "open",
        }
    return {"error": error_msg or "No project key returned"}


def export_l5k_grpc(project_key: str, output_path: str = "") -> dict:
    """Export an open project to L5K format via gRPC.

    Args:
        project_key: Project key from open_project_grpc
        output_path: Optional path to save L5K file. Defaults to /tmp/{project_key}.L5K

    Returns:
        Dict with file path and size, or error.
    """
    ensure_tunnel()
    stub = grpc_stub()
    req = pb.ProjectRequest(key=project_key)

    try:
        responses = list(stub.ExportToL5K(req, timeout=60))
    except grpc.RpcError as e:
        return {"error": f"gRPC error: {e.code()} — {e.details()[:200]}"}

    data = b"".join(
        r.data.string_value.encode("utf-8")
        for r in responses
        if r.HasField("data") and r.data.HasField("string_value")
    )

    if not data:
        return {"error": "Export returned no data"}

    if not output_path:
        output_path = f"/tmp/{project_key[:8]}.L5K"

    Path(output_path).write_bytes(data)

    # Quick parse
    sys.path.insert(0, "/tmp/LogixDesigner-MCP/src")
    from plc_parser.l5k import parse_l5k
    ctrl = parse_l5k(output_path)

    return {
        "file": output_path,
        "size_bytes": len(data),
        "controller": ctrl.name,
        "version": f"v{ctrl.major}.{ctrl.minor}",
        "processor": ctrl.processor_type,
        "tags": len(ctrl.tags),
        "programs": len(ctrl.programs),
        "routines": sum(len(p.routines) for p in ctrl.programs),
    }


def list_executables_grpc(project_key: str) -> dict:
    """List all executables (programs/routines) in an open project.

    Args:
        project_key: Project key from open_project_grpc

    Returns:
        Dict with count and list of XPATHs.
    """
    ensure_tunnel()
    stub = grpc_stub()
    req = pb.ProjectRequest(key=project_key)

    try:
        responses = list(stub.GetAllExecutables(req, timeout=15))
    except grpc.RpcError as e:
        return {"error": f"gRPC error: {e.code()} — {e.details()[:200]}"}

    xpaths = []
    for r in responses:
        if r.HasField("data") and r.data.HasField("string_array_value"):
            xpaths = list(r.data.string_array_value.values)

    return {
        "count": len(xpaths),
        "executables": xpaths[:50],  # Cap at 50 for response size
    }


def close_project_grpc(project_key: str) -> dict:
    """Close an open project via gRPC.

    Args:
        project_key: Project key from open_project_grpc
    """
    ensure_tunnel()
    stub = grpc_stub()
    req = pb.ProjectRequest(key=project_key)

    try:
        responses = list(stub.Close(req, timeout=15))
    except grpc.RpcError as e:
        return {"error": f"gRPC error: {e.code()} — {e.details()[:200]}"}

    name = _active_projects.pop(project_key, "unknown")
    return {"status": "closed", "file": name}


def token_status() -> dict:
    """Check auth token status."""
    if not os.path.exists(TOKEN_PATH):
        return {"status": "missing", "path": TOKEN_PATH}

    size = os.path.getsize(TOKEN_PATH)
    age_min = (time.time() - os.path.getmtime(TOKEN_PATH)) / 60
    return {
        "status": "valid" if age_min < 480 else "expired",
        "size_bytes": size,
        "age_minutes": round(age_min, 1),
        "active_projects": len(_active_projects),
    }


def parse_l5k_file(file_path: str) -> dict:
    """Parse an L5K file with the Python parser (no gRPC needed).

    Args:
        file_path: Path to L5K file (local or Windows path)

    Returns:
        Controller summary with tags, programs, routines.
    """
    try:
        sys.path.insert(0, "/tmp/LogixDesigner-MCP/src")
        from plc_parser.l5k import parse_l5k
        ctrl = parse_l5k(file_path)
    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}
    except Exception as e:
        return {"error": str(e)}

    aliases = [t for t in ctrl.tags if t.tag_type == "Alias"]
    bases = [t for t in ctrl.tags if t.tag_type == "Base"]

    return {
        "controller": ctrl.name,
        "version": f"v{ctrl.major}.{ctrl.minor}",
        "processor": ctrl.processor_type,
        "tags": len(ctrl.tags),
        "aliases": len(aliases),
        "base_tags": len(bases),
        "programs": len(ctrl.programs),
        "routines": sum(len(p.routines) for p in ctrl.programs),
        "sample_aliases": [
            {"name": t.name, "target": t.alias_for} for t in aliases[:5]
        ],
        "sample_tags": [
            {"name": t.name, "type": t.data_type, "scope": t.scope}
            for t in bases[:5]
        ],
        "programs_list": [
            {
                "name": p.name,
                "class": p.program_class,
                "routines": len(p.routines),
                "tags": len(p.tags),
            }
            for p in ctrl.programs
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# FastMCP Server
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from fastmcp import FastMCP

    mcp = FastMCP("Logix gRPC Client")

    mcp.tool()(open_project_grpc)
    mcp.tool()(export_l5k_grpc)
    mcp.tool()(list_executables_grpc)
    mcp.tool()(close_project_grpc)
    mcp.tool()(token_status)
    mcp.tool()(parse_l5k_file)

    # Start tunnel on launch
    ensure_tunnel()

    mcp.run(transport="stdio")
