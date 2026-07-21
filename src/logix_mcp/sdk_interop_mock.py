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
    TaskInfo,
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

    # --------------------------------------------------------------- save

    def save_acd(self, output_path: str) -> ExportResult:
        self._require_open()
        return ExportResult(
            path=output_path,
            size_bytes=1_048_576,
            routine_count=6,
        )

    # ------------------------------------------------------------- status

    def project_status(self) -> dict:
        return {
            "is_open": self._project_open,
            "project_path": self._project_path,
            "controller_name": "Test_Controller" if self._project_open else None,
        }

    # ---------------------------------------------------------- rung logic

    def get_rung_logic(self, program: str, routine: str) -> list[dict]:
        self._require_open()
        fake_rungs: dict[str, list[dict]] = {
            "MainRoutine": [
                {"rung": 0, "text": "XIC Motor_Start XIO Motor_Run OTE Motor_Run"},
                {"rung": 1, "text": "XIC Motor_Run TON Step_Timer ? ?"},
                {"rung": 2, "text": "XIC Step_Timer.DN OTE Cycle_Complete"},
                {"rung": 3, "text": "XIC Cycle_Complete ADD Cycle_Count 1 Cycle_Count"},
                {"rung": 4, "text": "XIC Fault_Reset OTU Fault_Latch"},
            ],
            "Alarm_Handler": [
                {"rung": 0, "text": "XIC Alarm_Trigger OTE Alarm_Active"},
                {"rung": 1, "text": "XIC Alarm_Active COP Alarm_History[0] Alarm_History[1] 31"},
            ],
            "Scaling": [
                {"rung": 0, "text": "Scaled_Value := (Raw_Input * 0.025) + Offset;"},
                {"rung": 1, "text": "IF Scaled_Value > Max_Limit THEN"},
                {"rung": 2, "text": "    Scaled_Value := Max_Limit;"},
                {"rung": 3, "text": "END_IF;"},
            ],
        }
        return fake_rungs.get(routine, [])

    # ------------------------------------------------------------- host

    def restart_host(self) -> dict:
        return {"restarted": True, "version": "33.01.00 (Mock)"}

    # ------------------------------------------------------------- tasks

    def get_task_structure(self) -> list[TaskInfo]:
        self._require_open()
        return [
            TaskInfo(
                name="MainTask",
                task_type="Continuous",
                rate_ms=None,
                priority=None,
                program_names=["MainProgram", "Motion_Control", "Safety_Gates"],
            ),
            TaskInfo(
                name="MotionTask",
                task_type="Periodic",
                rate_ms=10,
                priority=5,
                program_names=["Motion_Control"],
            ),
            TaskInfo(
                name="SafetyTask",
                task_type="Periodic",
                rate_ms=20,
                priority=1,
                program_names=["Safety_Gates"],
            ),
        ]

    # ------------------------------------------------------------ internal

    def _require_open(self) -> None:
        if not self._project_open:
            raise RuntimeError("No project open — call open_project() first")
