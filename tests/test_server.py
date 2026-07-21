"""Tests for the FastMCP server layer — tool wiring, error contract, async wrappers."""

import pytest
from fastmcp import FastMCP

from logix_mcp.models import (
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
from logix_mcp.server import create_app


def _unwrap(result):
    """Extract the structured payload from a FastMCP ToolResult."""
    if hasattr(result, "structured_content") and result.structured_content is not None:
        payload = result.structured_content
        if isinstance(payload, dict) and "result" in payload:
            return payload["result"]
        return payload
    return result


@pytest.fixture
def mcp() -> FastMCP:
    return create_app()


@pytest.mark.asyncio
async def test_server_get_sdk_info(mcp):
    result = await mcp.call_tool("get_sdk_info", {})
    data = _unwrap(result)
    assert isinstance(data, dict)
    assert data["sdk_available"] is True
    assert "Mock" in data["version"]


@pytest.mark.asyncio
async def test_server_open_and_close_project(mcp, tmp_path):
    fake_acd = tmp_path / "Test_Controller.ACD"
    fake_acd.write_bytes(b"FAKE")
    opened = _unwrap(await mcp.call_tool("open_project", {"path": str(fake_acd)}))
    assert isinstance(opened, dict)
    assert opened["name"] == "Test_Controller"

    closed = _unwrap(await mcp.call_tool("close_project", {}))
    assert isinstance(closed, dict)
    assert closed["closed"] is True


@pytest.mark.asyncio
async def test_server_export_requires_open_project(mcp, tmp_path):
    result = _unwrap(await mcp.call_tool("export_l5k", {"output_path": str(tmp_path / "out.L5K")}))
    assert isinstance(result, dict)
    assert result["code"] == "NO_PROJECT_OPEN"


@pytest.mark.asyncio
async def test_server_save_acd_requires_open_project(mcp, tmp_path):
    result = _unwrap(await mcp.call_tool("save_acd", {"output_path": str(tmp_path / "out.ACD")}))
    assert isinstance(result, dict)
    assert result["code"] == "NO_PROJECT_OPEN"


@pytest.mark.asyncio
async def test_server_project_status_no_project(mcp):
    status = _unwrap(await mcp.call_tool("project_status", {}))
    assert status["is_open"] is False
    assert status["project_path"] is None
    assert status["controller_name"] is None


@pytest.mark.asyncio
async def test_server_project_status_after_open(mcp, tmp_path):
    fake_acd = tmp_path / "Test_Controller.ACD"
    fake_acd.write_bytes(b"FAKE")
    await mcp.call_tool("open_project", {"path": str(fake_acd)})
    status = _unwrap(await mcp.call_tool("project_status", {}))
    assert status["is_open"] is True
    assert status["project_path"] == str(fake_acd)
    assert status["controller_name"] == "Test_Controller"


@pytest.mark.asyncio
async def test_server_get_rung_logic(mcp, tmp_path):
    fake_acd = tmp_path / "Test_Controller.ACD"
    fake_acd.write_bytes(b"FAKE")
    await mcp.call_tool("open_project", {"path": str(fake_acd)})
    rungs = _unwrap(await mcp.call_tool("get_rung_logic", {"program": "MainProgram", "routine": "MainRoutine"}))
    assert isinstance(rungs, list)
    assert len(rungs) > 0
    assert all("rung" in r and "text" in r for r in rungs)


@pytest.mark.asyncio
async def test_server_get_rung_logic_requires_open_project(mcp):
    result = _unwrap(await mcp.call_tool("get_rung_logic", {"program": "MainProgram", "routine": "MainRoutine"}))
    assert isinstance(result, dict)
    assert result["code"] == "NO_PROJECT_OPEN"


@pytest.mark.asyncio
async def test_server_restart_host(mcp):
    result = _unwrap(await mcp.call_tool("restart_host", {}))
    assert result["restarted"] is True
    assert "Mock" in result["version"]


@pytest.mark.asyncio
async def test_server_get_task_structure(mcp, tmp_path):
    fake_acd = tmp_path / "Test_Controller.ACD"
    fake_acd.write_bytes(b"FAKE")
    await mcp.call_tool("open_project", {"path": str(fake_acd)})
    tasks = _unwrap(await mcp.call_tool("get_task_structure", {}))
    assert isinstance(tasks, list)
    assert all(isinstance(t, dict) for t in tasks)
    names = {t["name"] for t in tasks}
    assert "MainTask" in names


@pytest.mark.asyncio
async def test_server_get_task_structure_requires_open_project(mcp):
    result = _unwrap(await mcp.call_tool("get_task_structure", {}))
    assert isinstance(result, dict)
    assert result["code"] == "NO_PROJECT_OPEN"


@pytest.mark.asyncio
async def test_server_error_contract_no_traceback(mcp):
    """Ensure no raw Python traceback leaks across the MCP boundary."""
    result = _unwrap(await mcp.call_tool("verify", {}))
    assert isinstance(result, dict)
    assert result["code"] == "NO_PROJECT_OPEN"
    # detail should not contain a traceback
    assert result["detail"] is None or "Traceback" not in result["detail"]
