"""Tests for MockSdkInterop behavior — tool-facing contracts."""

import pytest

from logix_mcp.models import (
    ControllerInfo,
    ExportResult,
    ProgramInfo,
    SdkInfo,
    TagDef,
    TaskInfo,
    VerifyResult,
)


def test_mock_get_info(mock_sdk):
    info = mock_sdk.get_info()
    assert isinstance(info, SdkInfo)
    assert info.sdk_available and info.studio_installed and info.licensed
    assert "Mock" in info.version


def test_open_project_returns_controller_info(mock_sdk, tmp_path):
    fake_acd = tmp_path / "Test_Controller.ACD"
    fake_acd.write_bytes(b"FAKE")
    ctrl = mock_sdk.open_project(str(fake_acd))
    assert isinstance(ctrl, ControllerInfo)
    assert ctrl.name == "Test_Controller"
    assert ctrl.type == "1756-L83E"
    assert ctrl.project_path == str(fake_acd)


def test_controller_tags_scopes(open_sdk):
    ctrl_tags = open_sdk.get_controller_tags()
    assert all(isinstance(t, TagDef) for t in ctrl_tags)
    names = {t.name for t in ctrl_tags}
    assert {"Motor_Run", "Fault_Reset"} <= names
    assert all(t.scope is None for t in ctrl_tags)

    prog_tags = open_sdk.get_controller_tags(scope="program:MainProgram")
    assert prog_tags, "program-scoped lookup should return tags"
    assert all(t.scope == "MainProgram" for t in prog_tags)
    assert all(t.tag_type == "Program" for t in prog_tags)


def test_program_structure_routine_counts(open_sdk):
    programs = open_sdk.get_program_structure()
    assert all(isinstance(p, ProgramInfo) for p in programs)
    names = [p.name for p in programs]
    assert "MainProgram" in names
    for p in programs:
        # routine_count must match actual routines list — internal consistency
        assert p.routine_count == len(p.routines)


def test_export_and_verify_require_open_project(mock_sdk, tmp_path):
    """Calling export/verify/tags with no open project raises RuntimeError."""
    with pytest.raises(RuntimeError, match="No project open"):
        mock_sdk.export_l5k(str(tmp_path / "out.L5K"))
    with pytest.raises(RuntimeError, match="No project open"):
        mock_sdk.export_l5x(str(tmp_path / "out.L5X"))
    with pytest.raises(RuntimeError, match="No project open"):
        mock_sdk.get_controller_tags()
    with pytest.raises(RuntimeError, match="No project open"):
        mock_sdk.verify()


def test_export_verify_happy_path(open_sdk, tmp_path):
    l5k = open_sdk.export_l5k(str(tmp_path / "out.L5K"))
    l5x = open_sdk.export_l5x(str(tmp_path / "out.L5X"))
    assert isinstance(l5k, ExportResult) and isinstance(l5x, ExportResult)
    assert l5k.size_bytes > 0 and l5x.size_bytes > 0
    # L5X is XML — typically larger than equivalent L5K
    assert l5x.size_bytes > l5k.size_bytes

    result = open_sdk.verify()
    assert isinstance(result, VerifyResult)
    assert result.passed
    assert result.errors == []


def test_close_project_releases_session(open_sdk):
    open_sdk.close_project()
    with pytest.raises(RuntimeError, match="No project open"):
        open_sdk.verify()


def test_import_l5k_round_trip(mock_sdk, tmp_path):
    fake_l5k = tmp_path / "export.L5K"
    fake_l5k.write_text("IE0.4,Logix Export File (Mock)")
    ctrl = mock_sdk.import_l5k(str(fake_l5k))
    assert isinstance(ctrl, ControllerInfo)
    assert ctrl.name == "Test_Controller"
    # After import, project is considered open — verify should work
    assert mock_sdk.verify().passed


def test_save_acd(open_sdk, tmp_path):
    out = tmp_path / "backup.ACD"
    result = open_sdk.save_acd(str(out))
    assert isinstance(result, ExportResult)
    assert result.path == str(out)
    assert result.size_bytes > 0


def test_save_acd_requires_open_project(mock_sdk, tmp_path):
    with pytest.raises(RuntimeError, match="No project open"):
        mock_sdk.save_acd(str(tmp_path / "backup.ACD"))


def test_project_status(open_sdk):
    status = open_sdk.project_status()
    assert status["is_open"] is True
    assert status["project_path"] is not None
    assert status["controller_name"] == "Test_Controller"


def test_project_status_closed(mock_sdk):
    status = mock_sdk.project_status()
    assert status["is_open"] is False
    assert status["project_path"] is None
    assert status["controller_name"] is None


def test_get_rung_logic(open_sdk):
    rungs = open_sdk.get_rung_logic("MainProgram", "MainRoutine")
    assert isinstance(rungs, list)
    assert len(rungs) > 0
    assert all(isinstance(r, dict) for r in rungs)
    assert all("rung" in r and "text" in r for r in rungs)
    # Rung numbers should be sequential
    numbers = [r["rung"] for r in rungs]
    assert numbers == list(range(len(rungs)))


def test_get_rung_logic_requires_open_project(mock_sdk):
    with pytest.raises(RuntimeError, match="No project open"):
        mock_sdk.get_rung_logic("MainProgram", "MainRoutine")


def test_restart_host(open_sdk):
    result = open_sdk.restart_host()
    assert result["restarted"] is True
    assert "Mock" in result["version"]


def test_get_task_structure(open_sdk):
    tasks = open_sdk.get_task_structure()
    assert all(isinstance(t, TaskInfo) for t in tasks)
    names = {t.name for t in tasks}
    assert "MainTask" in names
    continuous = [t for t in tasks if t.task_type == "Continuous"]
    periodic = [t for t in tasks if t.task_type == "Periodic"]
    assert len(continuous) == 1
    assert len(periodic) == 2
    assert all(t.rate_ms is not None for t in periodic)


def test_get_task_structure_requires_open_project(mock_sdk):
    with pytest.raises(RuntimeError, match="No project open"):
        mock_sdk.get_task_structure()
