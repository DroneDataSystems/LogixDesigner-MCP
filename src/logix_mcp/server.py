"""FastMCP server exposing the Logix Designer SDK as typed tools."""

import asyncio
import sys
from typing import Any

from fastmcp import FastMCP

from .models import (
    ControllerInfo,
    ExportResult,
    ProgramInfo,
    SdkError,
    SdkErrorCode,
    SdkInfo,
    TagDef,
    TaskInfo,
    VerifyResult,
)
from .sdk_interop import SdkInterop
from .sdk_interop_mock import MockSdkInterop


def _make_interop() -> SdkInterop:
    """Instantiate the correct SDK interop for the current platform."""
    if sys.platform == "win32":
        # Phase 4: RealSdkInterop will live here. For now, fall back to mock.
        try:
            from .sdk_interop_real import RealSdkInterop  # type: ignore[import-not-found]

            return RealSdkInterop()
        except ImportError:
            pass
    return MockSdkInterop()


def _classify_error(exc: Exception) -> SdkError:
    """Map Python exceptions to structured SdkError responses."""
    msg = str(exc)
    if "No project open" in msg:
        return SdkError(code=SdkErrorCode.NO_PROJECT_OPEN, message=msg)
    if "not licensed" in msg.lower() or "license" in msg.lower():
        return SdkError(code=SdkErrorCode.NOT_LICENSED, message=msg)
    if "already open" in msg.lower():
        return SdkError(code=SdkErrorCode.PROJECT_ALREADY_OPEN, message=msg)
    if "not found" in msg.lower() or "does not exist" in msg.lower():
        return SdkError(code=SdkErrorCode.NOT_FOUND, message=msg)
    if "timeout" in msg.lower():
        return SdkError(code=SdkErrorCode.TIMEOUT, message=msg)
    if "crash" in msg.lower() or "com" in msg.lower():
        return SdkError(code=SdkErrorCode.SDK_CRASHED, message=msg)
    return SdkError(code=SdkErrorCode.UNKNOWN, message=msg, detail=type(exc).__name__)


def create_app() -> FastMCP:
    """Build and return the FastMCP server instance."""
    mcp = FastMCP("logix-mcp")
    interop = _make_interop()

    async def _call(func, *args, **kwargs):
        """Run a sync interop call in a thread and wrap errors."""
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as exc:
            return _classify_error(exc)

    # ---------------------------------------------------------------
    # Info
    # ---------------------------------------------------------------

    @mcp.tool()
    async def get_sdk_info() -> SdkInfo | SdkError:
        """Get SDK status, version, and license info."""
        return await _call(interop.get_info)

    # ---------------------------------------------------------------
    # Project lifecycle
    # ---------------------------------------------------------------

    @mcp.tool()
    async def open_project(path: str) -> ControllerInfo | SdkError:
        """Open an ACD project file. Returns controller info."""
        return await _call(interop.open_project, path)

    @mcp.tool()
    async def close_project() -> dict[str, Any] | SdkError:
        """Close the currently open project."""
        result = await _call(interop.close_project)
        if isinstance(result, SdkError):
            return result
        return {"closed": True}

    @mcp.tool()
    async def save_acd(output_path: str) -> ExportResult | SdkError:
        """Save the open project as an ACD file."""
        return await _call(interop.save_acd, output_path)

    @mcp.tool()
    async def project_status() -> dict[str, Any]:
        """Return current project open state and metadata."""
        # status never raises — no try/except needed
        return await asyncio.to_thread(interop.project_status)

    # ---------------------------------------------------------------
    # Export / Import
    # ---------------------------------------------------------------

    @mcp.tool()
    async def export_l5k(output_path: str) -> ExportResult | SdkError:
        """Export open project to L5K text format."""
        return await _call(interop.export_l5k, output_path)

    @mcp.tool()
    async def export_l5x(output_path: str) -> ExportResult | SdkError:
        """Export open project to L5X XML format."""
        return await _call(interop.export_l5x, output_path)

    @mcp.tool()
    async def import_l5k(input_path: str) -> ControllerInfo | SdkError:
        """Import an L5K file (create ACD from text export)."""
        return await _call(interop.import_l5k, input_path)

    # ---------------------------------------------------------------
    # Tags & Structure
    # ---------------------------------------------------------------

    @mcp.tool()
    async def get_controller_tags(scope: str | None = None) -> list[TagDef] | SdkError:
        """List controller-scope tags. Pass scope='program:Name' for program tags."""
        return await _call(interop.get_controller_tags, scope)

    @mcp.tool()
    async def get_program_structure() -> list[ProgramInfo] | SdkError:
        """Get full program/routine/rung tree of the open project."""
        return await _call(interop.get_program_structure)

    @mcp.tool()
    async def get_rung_logic(program: str, routine: str) -> list[dict[str, Any]] | SdkError:
        """Return rung-by-rung logic for a given routine."""
        return await _call(interop.get_rung_logic, program, routine)

    @mcp.tool()
    async def get_task_structure() -> list[TaskInfo] | SdkError:
        """Return the controller task configuration."""
        return await _call(interop.get_task_structure)

    # ---------------------------------------------------------------
    # Verification
    # ---------------------------------------------------------------

    @mcp.tool()
    async def verify() -> VerifyResult | SdkError:
        """Run controller verification. Returns errors/warnings."""
        return await _call(interop.verify)

    # ---------------------------------------------------------------
    # Host management
    # ---------------------------------------------------------------

    @mcp.tool()
    async def restart_host() -> dict[str, Any]:
        """Kill and restart the SDK COM host process (recovery)."""
        # restart_host is always safe to call; it never raises
        return await asyncio.to_thread(interop.restart_host)

    return mcp
