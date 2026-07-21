"""Abstract interface for Logix Designer SDK operations.

Real implementation uses pythonnet COM (Windows only).
Mock implementation used for Linux testing.
"""

from abc import ABC, abstractmethod

from .models import (
    ControllerInfo,
    ExportResult,
    ProgramInfo,
    SdkInfo,
    TagDef,
    TaskInfo,
    VerifyResult,
)


class SdkInterop(ABC):
    """Abstract interface for Logix Designer SDK operations."""

    @abstractmethod
    def get_info(self) -> SdkInfo:
        """Get SDK status, version, and license info."""
        ...

    @abstractmethod
    def open_project(self, path: str) -> ControllerInfo:
        """Open an ACD project file. Returns controller info."""
        ...

    @abstractmethod
    def close_project(self) -> None:
        """Close the currently open project."""
        ...

    @abstractmethod
    def export_l5k(self, output_path: str) -> ExportResult:
        """Export open project to L5K text format."""
        ...

    @abstractmethod
    def export_l5x(self, output_path: str) -> ExportResult:
        """Export open project to L5X XML format."""
        ...

    @abstractmethod
    def import_l5k(self, input_path: str) -> ControllerInfo:
        """Import an L5K file (create ACD from text export)."""
        ...

    @abstractmethod
    def get_controller_tags(self, scope: str | None = None) -> list[TagDef]:
        """List controller-scope tags. Pass scope='program:Name' for program tags."""
        ...

    @abstractmethod
    def get_program_structure(self) -> list[ProgramInfo]:
        """Get full program/routine/rung tree of the open project."""
        ...

    @abstractmethod
    def verify(self) -> VerifyResult:
        """Run controller verification. Returns errors/warnings."""
        ...

    @abstractmethod
    def save_acd(self, output_path: str) -> ExportResult:
        """Save the open project as an ACD file."""
        ...

    @abstractmethod
    def project_status(self) -> dict:
        """Return current project open state and metadata."""
        ...

    @abstractmethod
    def get_rung_logic(self, program: str, routine: str) -> list[dict]:
        """Return rung-by-rung logic for a given routine.

        Each dict should contain at least:
          - rung: int
          - text: str  (e.g. ladder logic or ST source)
        """
        ...

    @abstractmethod
    def restart_host(self) -> dict:
        """Kill and restart the SDK COM host process (recovery)."""
        ...

    @abstractmethod
    def get_task_structure(self) -> list[TaskInfo]:
        """Return the controller task configuration."""
        ...
