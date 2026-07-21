"""Pydantic response models — the stable contract for all MCP tools."""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class SdkErrorCode(str, Enum):
    """Structured error codes for SDK failures."""
    NOT_FOUND = "NOT_FOUND"
    NOT_LICENSED = "NOT_LICENSED"
    PROJECT_ALREADY_OPEN = "PROJECT_ALREADY_OPEN"
    NO_PROJECT_OPEN = "NO_PROJECT_OPEN"
    SDK_CRASHED = "SDK_CRASHED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class SdkError(BaseModel):
    """Structured error returned by all MCP tools on failure."""
    code: SdkErrorCode
    message: str
    detail: str | None = None


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


class TaskInfo(BaseModel):
    """Controller task (continuous, periodic, event)."""
    name: str
    task_type: str          # "Continuous", "Periodic", "Event"
    rate_ms: int | None     # scan rate for periodic tasks
    priority: int | None
    program_names: list[str]
