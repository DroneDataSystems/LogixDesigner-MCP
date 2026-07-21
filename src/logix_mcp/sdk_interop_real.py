"""Real Logix Designer SDK interop — installed via .whl on Windows.

Requires:
  pip install "<SDK_PATH>\\python\\logix_designer_sdk-*.whl"

The SDK is an async Python client communicating with LdSdkServer.dll (TCP 53204).
We bridge from our sync SdkInterop ABC using asyncio.run().
"""
import asyncio
import sys
from typing import Any

from logix_mcp.models import (
    ControllerInfo,
    ExportResult,
    ProgramInfo,
    RoutineInfo,
    SdkError,
    SdkErrorCode,
    SdkInfo,
    TagDef,
    TaskInfo,
    VerifyResult,
)
from logix_mcp.sdk_interop import SdkInterop

# The SDK may be importable or may raise on missing dependencies.
# Defer the import so the module at least loads for type-checking.
try:
    from logix_designer_sdk.logix_project import LogixProject
    from logix_designer_sdk.common.event_logger import StdOutEventLogger
    from logix_designer_sdk.common.exceptions import LogixSdkException

    SDK_AVAILABLE = True
except ImportError:
    LogixProject = None  # type: ignore
    StdOutEventLogger = None  # type: ignore
    LogixSdkException = Exception  # type: ignore
    SDK_AVAILABLE = False


def _run_async(coro):
    """Run an async SDK call synchronously, bridging to our ABC."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Already in an event loop — use a thread-safe alternative
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _logix_sdk_error(exc: Exception, context: str = "") -> SdkError:
    """Map LogixSdkException to our structured SdkError."""
    msg = str(exc)
    lower = msg.lower()
    if "not found" in lower or "does not exist" in lower:
        code = SdkErrorCode.NOT_FOUND
    elif "license" in lower or "licensed" in lower:
        code = SdkErrorCode.NOT_LICENSED
    elif "already open" in lower:
        code = SdkErrorCode.PROJECT_ALREADY_OPEN
    elif "timeout" in lower:
        code = SdkErrorCode.TIMEOUT
    else:
        code = SdkErrorCode.UNKNOWN
    detail = f"{context}: {msg}" if context else msg
    return SdkError(code=code, message=msg, detail=detail)


class RealSdkInterop(SdkInterop):
    """Real implementation using the Logix Designer SDK Python client."""

    def __init__(self) -> None:
        if not SDK_AVAILABLE:
            raise ImportError(
                "logix_designer_sdk is not installed. "
                "Install the SDK .whl from: "
                r"C:\Users\Public\Documents\Studio 5000\Logix Designer SDK\python\\"
            )
        self._project: "LogixProject | None" = None
        self._project_path: str | None = None
        self._logger = StdOutEventLogger()

    # ------------------------------------------------------------------ info

    def get_info(self) -> SdkInfo:
        return SdkInfo(
            version=_run_async(self._get_version()),
            sdk_available=SDK_AVAILABLE,
            studio_installed=True,
            licensed=True,  # Assumed — SDK raises LogixSdkException if not
        )

    async def _get_version(self) -> str:
        try:
            # Open a temp project to read version info, or use SDK metadata
            # For now, return a placeholder since we need an ACD to check
            return "2.01+"  # SDK version; actual Logix Designer version from open_project
        except Exception:
            return "unknown"

    # -------------------------------------------------------------- project

    def open_project(self, path: str) -> ControllerInfo:
        async def _open():
            self._project = await LogixProject.open_logix_project(
                path, self._logger
            )
            self._project_path = path
            # Extract controller info from the project
            return ControllerInfo(
                name="Controller",  # SDK doesn't expose name directly — infer from path
                type="Unknown",  # Need to query controller type
                revision="Unknown",  # Need to query revision
                project_path=path,
            )

        try:
            return _run_async(_open())
        except LogixSdkException as e:
            raise RuntimeError(str(e)) from e

    def close_project(self) -> None:
        self._project = None
        self._project_path = None

    # -------------------------------------------------------------- save

    def save_acd(self, output_path: str) -> ExportResult:
        self._require_open()

        async def _save():
            await self._project.SaveAsAsync(output_path, True)
            import os
            size = os.path.getsize(output_path)
            return ExportResult(
                path=output_path,
                size_bytes=size,
                routine_count=0,  # SDK doesn't expose routine count in save result
            )

        try:
            return _run_async(_save())
        except LogixSdkException as e:
            raise RuntimeError(str(e)) from e

    # -------------------------------------------------------------- export

    def export_l5k(self, output_path: str) -> ExportResult:
        self._require_open()
        return self._export_impl(output_path)

    def export_l5x(self, output_path: str) -> ExportResult:
        self._require_open()
        return self._export_impl(output_path)

    def _export_impl(self, output_path: str) -> ExportResult:
        """SaveAs figures out format from extension (.L5K, .L5X, .ACD)."""
        async def _export():
            await self._project.SaveAsAsync(output_path, True)
            import os
            size = os.path.getsize(output_path)
            return ExportResult(
                path=output_path,
                size_bytes=size,
                routine_count=0,
            )

        try:
            return _run_async(_export())
        except LogixSdkException as e:
            raise RuntimeError(str(e)) from e

    # -------------------------------------------------------------- import

    def import_l5k(self, input_path: str) -> ControllerInfo:
        """Import L5K by converting to current version then saving as ACD."""
        import os

        async def _import():
            # Use ConvertAsync to load the L5K into a LogixProject
            # Major revision 0 means "latest installed"
            self._project = await LogixProject.ConvertAsync(input_path, 0)
            self._project_path = input_path
            return ControllerInfo(
                name=os.path.splitext(os.path.basename(input_path))[0],
                type="Unknown",
                revision="Unknown",
                project_path=input_path,
            )

        try:
            return _run_async(_import())
        except LogixSdkException as e:
            raise RuntimeError(str(e)) from e

    # ---------------------------------------------------------------- tags

    def get_controller_tags(self, scope: str | None = None) -> list[TagDef]:
        self._require_open()
        # The SDK uses XPath to query project structure.
        # Tag enumeration requires walking the project XML or using GetAllExecutables.
        # For now, return what we can.
        return []  # TODO: implement via XPath queries or PartialExport

    # ----------------------------------------------------------- structure

    def get_program_structure(self) -> list[ProgramInfo]:
        self._require_open()

        async def _get():
            executables = await self._project.get_all_executables()
            # executables is a list of XPath strings.
            # Parse to extract program/routine structure.
            programs: dict[str, list[RoutineInfo]] = {}
            for xpath in executables:
                # XPaths look like:
                # /Controller/Programs/Program[@Name='MainProgram']/Routines/Routine[@Name='MainRoutine']
                if "/Programs/Program" in xpath and "/Routines/Routine" in xpath:
                    import re
                    prog_match = re.search(r"Program\[@Name='([^']+)'\]", xpath)
                    rout_match = re.search(r"Routine\[@Name='([^']+)'\]", xpath)
                    if prog_match and rout_match:
                        prog_name = prog_match.group(1)
                        rout_name = rout_match.group(1)
                        if prog_name not in programs:
                            programs[prog_name] = []
                        programs[prog_name].append(
                            RoutineInfo(name=rout_name, rung_count=0, language="Ladder")
                        )

            return [
                ProgramInfo(
                    name=name,
                    routine_count=len(routines),
                    routines=routines,
                )
                for name, routines in programs.items()
            ]

        try:
            return _run_async(_get())
        except LogixSdkException as e:
            raise RuntimeError(str(e)) from e

    def get_rung_logic(self, program: str, routine: str) -> list[dict[str, Any]]:
        self._require_open()
        # Export the specific routine to L5X and parse rung text.
        # This requires PartialExportToXmlFileAsync then parsing the L5X.
        return []  # TODO: implement via PartialExport + L5X parsing

    def get_task_structure(self) -> list[TaskInfo]:
        self._require_open()
        # Task structure requires XPath queries into the controller XML.
        return []  # TODO: implement via PartialExport or SDK task queries

    # -------------------------------------------------------------- verify

    def verify(self) -> VerifyResult:
        self._require_open()
        # The SDK doesn't expose verify directly.
        # Attempt a SaveAs to temp to validate the project compiles.
        import tempfile
        import os

        async def _verify():
            tmp = tempfile.mktemp(suffix=".ACD")
            try:
                await self._project.SaveAsAsync(tmp, True)
                return VerifyResult(errors=[], warnings=[], passed=True)
            except LogixSdkException as e:
                return VerifyResult(errors=[str(e)], warnings=[], passed=False)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)

        try:
            return _run_async(_verify())
        except LogixSdkException as e:
            return VerifyResult(errors=[str(e)], warnings=[], passed=False)

    # --------------------------------------------------------- host mgmt

    def restart_host(self) -> dict[str, Any]:
        """Restart the SDK server by killing and reconnecting."""
        # LdSdkServer.dll runs as a separate process on port 53204.
        # Killing and restarting is managed externally (e.g., via deploy script).
        return {"restarted": False, "note": "Restart managed via Windows service"}

    # ------------------------------------------------------------- status

    def project_status(self) -> dict[str, Any]:
        return {
            "is_open": self._project is not None,
            "project_path": self._project_path,
            "controller_name": "Unknown" if self._project else None,
        }

    # ------------------------------------------------------------ internal

    def _require_open(self) -> None:
        if self._project is None:
            raise RuntimeError("No project open — call open_project() first")
