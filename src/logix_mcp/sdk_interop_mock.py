"""Mock SDK interop for Linux testing.

Returns realistic fake data: controller "Test_Controller", tags like
"Motor_Run" / "Fault_Reset", programs/routines, and clean verification.
"""

from .models import (
    ControllerInfo,
    ExportResult,
    ProgramInfo,
    RoutineInfo,
    SdkInfo,
    TagDef,
    VerifyResult,
)
from .sdk_interop import SdkInterop


class MockSdkInterop(SdkInterop):
    """Fake Logix Designer SDK for Linux-side development and tests."""

    def __init__(self) -> None:
        self._project_open = False
        self._project_path: str | None = None

    # ------------------------------------------------------------------ info

    def get_info(self) -> SdkInfo:
        return SdkInfo(
            version="33.01.00 (Mock)",
            sdk_available=True,
            studio_installed=True,
            licensed=True,
        )

    # -------------------------------------------------------------- project

    def open_project(self, path: str) -> ControllerInfo:
        self._project_open = True
        self._project_path = path
        return ControllerInfo(
            name="Test_Controller",
            type="1756-L83E",
            revision="33.011",
            project_path=path,
        )

    def close_project(self) -> None:
        self._project_open = False
        self._project_path = None

    # -------------------------------------------------------------- export

    def export_l5k(self, output_path: str) -> ExportResult:
        self._require_open()
        return ExportResult(
            path=output_path,
            size_bytes=248_913,
            routine_count=6,
        )

    def export_l5x(self, output_path: str) -> ExportResult:
        self._require_open()
        return ExportResult(
            path=output_path,
            size_bytes=412_377,
            routine_count=6,
        )

    def import_l5k(self, input_path: str) -> ControllerInfo:
        self._project_open = True
        self._project_path = input_path
        return ControllerInfo(
            name="Test_Controller",
            type="1756-L83E",
            revision="33.011",
            project_path=input_path,
        )

    # ---------------------------------------------------------------- tags

    def get_controller_tags(self, scope: str | None = None) -> list[TagDef]:
        self._require_open()
        if scope is not None and scope.startswith("program:"):
            program = scope.split(":", 1)[1]
            return [
                TagDef(
                    name="Cycle_Count",
                    tag_type="Program",
                    data_type="DINT",
                    description="Machine cycle counter",
                    scope=program,
                ),
                TagDef(
                    name="Step_Timer",
                    tag_type="Program",
                    data_type="TIMER",
                    description="Sequence step timer",
                    scope=program,
                ),
            ]
        return [
            TagDef(
                name="Motor_Run",
                tag_type="Controller",
                data_type="BOOL",
                description="Main motor run command",
                scope=None,
            ),
            TagDef(
                name="Fault_Reset",
                tag_type="Controller",
                data_type="BOOL",
                description="Global fault reset pushbutton",
                scope=None,
            ),
            TagDef(
                name="Conveyor_Speed_SP",
                tag_type="Controller",
                data_type="REAL",
                description="Conveyor speed setpoint (FPM)",
                scope=None,
            ),
            TagDef(
                name="Alarm_History",
                tag_type="Controller",
                data_type="UDT_Alarm[32]",
                description="Circular buffer of recent alarms",
                scope=None,
            ),
        ]

    # ----------------------------------------------------------- structure

    def get_program_structure(self) -> list[ProgramInfo]:
        self._require_open()
        return [
            ProgramInfo(
                name="MainProgram",
                routine_count=3,
                routines=[
                    RoutineInfo(name="MainRoutine", rung_count=42, language="Ladder"),
                    RoutineInfo(name="Alarm_Handler", rung_count=17, language="Ladder"),
                    RoutineInfo(name="Scaling", rung_count=8, language="ST"),
                ],
            ),
            ProgramInfo(
                name="Motion_Control",
                routine_count=2,
                routines=[
                    RoutineInfo(name="Axis_Home", rung_count=23, language="Ladder"),
                    RoutineInfo(name="Cam_Profile", rung_count=11, language="FBD"),
                ],
            ),
            ProgramInfo(
                name="Safety_Gates",
                routine_count=1,
                routines=[
                    RoutineInfo(name="Gate_Monitor", rung_count=15, language="Ladder"),
                ],
            ),
        ]

    # -------------------------------------------------------------- verify

    def verify(self) -> VerifyResult:
        self._require_open()
        return VerifyResult(errors=[], warnings=[], passed=True)

    # ------------------------------------------------------------ internal

    def _require_open(self) -> None:
        if not self._project_open:
            raise RuntimeError("No project open — call open_project() first")
