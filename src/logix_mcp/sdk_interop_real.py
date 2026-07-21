"""Real Logix Designer SDK interop — installed via .whl on Windows.

SDK v2.0.2 is a synchronous Python client. No asyncio, no COM.
Communicates with LdSdkServer.dll (TCP 53204).

Install:  pip install "<SDK_PATH>\\python\\logix_designer_sdk-2.0.2-py3-none-any.whl"
"""

import os
import re
import tempfile
from typing import Any
from xml.etree import ElementTree as ET

from logix_designer_sdk import LogixProject, StdOutEventLogger
from logix_designer_sdk.exceptions import LogixSdkError

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

# L5X namespace used in partial exports for tag/task/rung parsing
L5X_NS = "http://www.rockwellautomation.com/xml/schemas/L5X"


class RealSdkInterop(SdkInterop):
    """Real implementation using the Logix Designer SDK Python client (v2.0.2)."""

    def __init__(self) -> None:
        self._project: LogixProject | None = None
        self._project_path: str | None = None

    # ── info ────────────────────────────────────────────────────────────

    def get_info(self) -> SdkInfo:
        return SdkInfo(
            version="2.0.2",
            sdk_available=True,
            studio_installed=True,
            licensed=True,
        )

    # ── project lifecycle ───────────────────────────────────────────────

    def open_project(self, path: str) -> ControllerInfo:
        self._project = LogixProject.open_logix_project(path)
        self._project_path = path
        name = os.path.splitext(os.path.basename(path))[0]
        return ControllerInfo(
            name=name,
            type="Unknown",       # SDK doesn't expose processor type directly
            revision="Unknown",   # revision available after project inspection
            project_path=path,
        )

    def close_project(self) -> None:
        self._project = None
        self._project_path = None

    def save_acd(self, output_path: str) -> ExportResult:
        self._require_open()
        self._project.save_as(output_path)
        size = os.path.getsize(output_path)
        return ExportResult(path=output_path, size_bytes=size, routine_count=0)

    # ── export / import ─────────────────────────────────────────────────

    def export_l5k(self, output_path: str) -> ExportResult:
        self._require_open()
        return self._export_impl(output_path)

    def export_l5x(self, output_path: str) -> ExportResult:
        self._require_open()
        return self._export_impl(output_path)

    def _export_impl(self, output_path: str) -> ExportResult:
        # save_as uses file extension to determine format (L5K, L5X, ACD)
        self._project.save_as(output_path)
        size = os.path.getsize(output_path)
        return ExportResult(path=output_path, size_bytes=size, routine_count=0)

    def import_l5k(self, input_path: str) -> ControllerInfo:
        # convert(project_path, destination_revision) — 0 = latest installed
        self._project = LogixProject.convert(input_path, 0)
        self._project_path = input_path
        name = os.path.splitext(os.path.basename(input_path))[0]
        return ControllerInfo(
            name=name, type="Unknown", revision="Unknown", project_path=input_path,
        )

    # ── tags ────────────────────────────────────────────────────────────

    def get_controller_tags(self, scope: str | None = None) -> list[TagDef]:
        self._require_open()
        try:
            if scope and scope.startswith("program:"):
                prog = scope.split(":", 1)[1]
                xpath = f"/Controller/Programs/Program[@Name='{prog}']/Tags"
                tag_type = "Program"
            else:
                xpath = "/Controller/Tags"
                tag_type = "Controller"

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_xml = os.path.join(tmpdir, "tags.L5X")
                self._project.partial_export_to_xml_file(xpath, tmp_xml)
                return _parse_tags_from_l5x(tmp_xml, tag_type, scope)
        except LogixSdkError:
            return []

    # ── structure ───────────────────────────────────────────────────────

    def get_program_structure(self) -> list[ProgramInfo]:
        self._require_open()
        xpaths = self._project.get_all_executables()
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

    def get_rung_logic(self, program: str, routine: str) -> list[dict[str, Any]]:
        self._require_open()
        try:
            xpath = (
                f"/Controller/Programs/Program[@Name='{program}']"
                f"/Routines/Routine[@Name='{routine}']"
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_xml = os.path.join(tmpdir, "rung.L5X")
                self._project.partial_export_to_xml_file(xpath, tmp_xml)
                return _parse_rungs_from_l5x(tmp_xml)
        except LogixSdkError:
            return []

    def get_task_structure(self) -> list[TaskInfo]:
        self._require_open()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_xml = os.path.join(tmpdir, "tasks.L5X")
                self._project.partial_export_to_xml_file("/Controller/Tasks", tmp_xml)
                return _parse_tasks_from_l5x(tmp_xml)
        except LogixSdkError:
            return []

    # ── verify ──────────────────────────────────────────────────────────

    def verify(self) -> VerifyResult:
        self._require_open()
        tmp = tempfile.mktemp(suffix=".ACD")
        try:
            self._project.save_as(tmp, force=True)
            return VerifyResult(errors=[], warnings=[], passed=True)
        except LogixSdkError as e:
            return VerifyResult(errors=[str(e)], warnings=[], passed=False)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    # ── host management ─────────────────────────────────────────────────

    def restart_host(self) -> dict[str, Any]:
        return {"restarted": False, "note": "Restart managed via Windows service"}

    # ── status ──────────────────────────────────────────────────────────

    def project_status(self) -> dict[str, Any]:
        return {
            "is_open": self._project is not None,
            "project_path": self._project_path,
            "controller_name": "Unknown" if self._project else None,
        }

    # ── internal ────────────────────────────────────────────────────────

    def _require_open(self) -> None:
        if self._project is None:
            raise RuntimeError("No project open — call open_project() first")


# ═══════════════════════════════════════════════════════════════════════════
# L5X partial-export parsers
# ═══════════════════════════════════════════════════════════════════════════

RSLOGIX5000_CONTENT = "RSLogix5000Content"

NS = {"ns": L5X_NS}


def _parse_tags_from_l5x(
    path: str, tag_type: str, scope: str | None
) -> list[TagDef]:
    """Parse controller or program-scope tags from a partial L5X export."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError:
        return []

    # Handle RSLogix5000Content wrapper
    inner = root.find(f"{{{L5X_NS}}}{RSLOGIX5000_CONTENT}")
    if inner is not None:
        root = inner

    tags: list[TagDef] = []
    for tag_el in root.findall(".//ns:Tag", NS):
        name = tag_el.get("Name", "")
        data_type = tag_el.get("DataType", "")
        desc = tag_el.get("Description", "") or ""
        tags.append(
            TagDef(
                name=name,
                tag_type=tag_type,
                data_type=data_type,
                description=desc,
                scope=scope.split(":", 1)[1] if scope and scope.startswith("program:") else None,
            )
        )
    return tags


def _parse_rungs_from_l5x(path: str) -> list[dict[str, Any]]:
    """Parse rung text from a partial L5X export of a routine."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError:
        return []

    inner = root.find(f"{{{L5X_NS}}}{RSLOGIX5000_CONTENT}")
    if inner is not None:
        root = inner

    rungs: list[dict[str, Any]] = []
    for i, rung_el in enumerate(root.findall(".//ns:Rung", NS)):
        number = int(rung_el.get("Number", str(i)))
        comment_el = rung_el.find("ns:Comment", NS)
        text_el = rung_el.find("ns:Text", NS)
        rungs.append({
            "rung": number,
            "text": (text_el.text or "") if text_el is not None else "",
            "comment": (comment_el.text or "") if comment_el is not None else "",
        })
    return rungs


def _parse_tasks_from_l5x(path: str) -> list[TaskInfo]:
    """Parse task configuration from a partial L5X export."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError:
        return []

    inner = root.find(f"{{{L5X_NS}}}{RSLOGIX5000_CONTENT}")
    if inner is not None:
        root = inner

    tasks: list[TaskInfo] = []
    for task_el in root.findall(".//ns:Task", NS):
        name = task_el.get("Name", "")
        task_type = task_el.get("Type", "")
        rate = task_el.get("Rate")
        priority = task_el.get("Priority")
        program_names: list[str] = []
        for sp in task_el.findall(".//ns:ScheduledProgram", NS):
            pn = sp.get("Name", "")
            if pn:
                program_names.append(pn)

        rate_ms: int | None = None
        if rate is not None:
            try:
                rate_ms = int(float(rate) * 1000)
            except (ValueError, TypeError):
                pass

        pri: int | None = None
        if priority is not None:
            try:
                pri = int(priority)
            except (ValueError, TypeError):
                pass

        tasks.append(TaskInfo(
            name=name,
            task_type=task_type,
            rate_ms=rate_ms,
            priority=pri,
            program_names=program_names,
        ))
    return tasks
