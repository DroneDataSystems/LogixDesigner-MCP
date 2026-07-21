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
