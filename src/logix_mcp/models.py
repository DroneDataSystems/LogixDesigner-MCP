"""Pydantic response models — the stable contract for all MCP tools."""

from pydantic import BaseModel


class SdkInfo(BaseModel):
    version: str
    sdk_available: bool
    studio_installed: bool
    licensed: bool


class ControllerInfo(BaseModel):
    name: str
    type: str           # e.g. "1756-L83E"
    revision: str       # e.g. "33.011"
    project_path: str


class TagDef(BaseModel):
    name: str
    tag_type: str       # "Controller", "Program"
    data_type: str      # "DINT", "TIMER", "UDT_Name"
    description: str
    scope: str | None


class RoutineInfo(BaseModel):
    name: str
    rung_count: int
    language: str       # "Ladder", "ST", "FBD", "SFC"


class ProgramInfo(BaseModel):
    name: str
    routine_count: int
    routines: list[RoutineInfo]


class VerifyResult(BaseModel):
    errors: list[str]
    warnings: list[str]
    passed: bool


class ExportResult(BaseModel):
    path: str
    size_bytes: int
    routine_count: int
