"""Tests for Pydantic response models — serialization round-trips and edge cases."""

from logix_mcp.models import (
    ControllerInfo,
    ExportResult,
    ProgramInfo,
    RoutineInfo,
    SdkInfo,
    TagDef,
    VerifyResult,
)


def test_sdk_info_json_round_trip():
    info = SdkInfo(version="33.01.00", sdk_available=True, studio_installed=True, licensed=True)
    restored = SdkInfo.model_validate_json(info.model_dump_json())
    assert restored == info


def test_controller_info_json_round_trip():
    ctrl = ControllerInfo(
        name="Test_Controller",
        type="1756-L83E",
        revision="33.011",
        project_path="C:\\Projects\\Test_Controller.ACD",
    )
    restored = ControllerInfo.model_validate_json(ctrl.model_dump_json())
    assert restored == ctrl
    assert restored.type == "1756-L83E"


def test_tagdef_optional_scope():
    """Controller-scope tags have scope=None; program tags carry the scope."""
    ctrl_tag = TagDef(
        name="Motor_Run", tag_type="Controller", data_type="BOOL",
        description="Main motor run command", scope=None,
    )
    prog_tag = TagDef(
        name="Cycle_Count", tag_type="Program", data_type="DINT",
        description="Counter", scope="MainProgram",
    )
    assert ctrl_tag.model_dump()["scope"] is None
    assert prog_tag.scope == "MainProgram"
    # Round-trip both
    assert TagDef.model_validate_json(ctrl_tag.model_dump_json()) == ctrl_tag
    assert TagDef.model_validate_json(prog_tag.model_dump_json()) == prog_tag


def test_program_info_nested_routines():
    prog = ProgramInfo(
        name="MainProgram",
        routine_count=2,
        routines=[
            RoutineInfo(name="MainRoutine", rung_count=42, language="Ladder"),
            RoutineInfo(name="Scaling", rung_count=8, language="ST"),
        ],
    )
    data = prog.model_dump()
    assert data["routine_count"] == 2
    assert len(data["routines"]) == 2
    assert data["routines"][0]["language"] == "Ladder"
    restored = ProgramInfo.model_validate(data)
    assert restored == prog


def test_verify_result_pass_and_fail_shapes():
    passed = VerifyResult(errors=[], warnings=[], passed=True)
    failed = VerifyResult(
        errors=["Rung 5: Destructive instruction without seal-in"],
        warnings=["Tag 'Unused_1' never referenced"],
        passed=False,
    )
    assert passed.passed and not passed.errors
    assert not failed.passed
    assert len(failed.errors) == 1 and len(failed.warnings) == 1
    assert VerifyResult.model_validate_json(failed.model_dump_json()) == failed


def test_export_result_fields():
    result = ExportResult(path="/tmp/out.L5K", size_bytes=248913, routine_count=6)
    data = result.model_dump()
    assert data == {"path": "/tmp/out.L5K", "size_bytes": 248913, "routine_count": 6}
