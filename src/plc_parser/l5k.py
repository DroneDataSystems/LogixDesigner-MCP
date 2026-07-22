"""L5K Parser — Parse Rockwell RSLogix 5000 L5K export format.

IE_VER 2.24 format. Parses:
  - Controller metadata (name, processor type, revision)
  - Controller-scope tags (aliases, base, UDT members)
  - Programs with routines and program-scope tags
  - Data types, modules, tasks

Usage:
    from plc_parser.l5k import parse_l5k
    controller = parse_l5k("path/to/export.L5K")
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Data model ────────────────────────────────────────────────────────

@dataclass
class TagDef:
    name: str
    tag_type: str = "Base"  # Base, Alias, Produced, Consumed
    data_type: str = "DINT"
    description: str = ""
    dimensions: list[int] = field(default_factory=list)
    value: Optional[str] = None
    alias_for: Optional[str] = None
    scope: str = "controller"

@dataclass
class RoutineDef:
    name: str
    language: str = "Ladder"  # RLL, ST, FBD, SFC
    rungs: int = 0

@dataclass
class ProgramDef:
    name: str
    program_class: str = "Standard"
    routines: list[RoutineDef] = field(default_factory=list)
    tags: list[TagDef] = field(default_factory=list)

@dataclass
class DataTypeDef:
    name: str
    members: list[TagDef] = field(default_factory=list)

@dataclass
class ControllerDef:
    name: str
    processor_type: str = ""
    major: int = 0
    minor: int = 0
    ie_ver: str = "2.24"
    description: str = ""
    tags: list[TagDef] = field(default_factory=list)
    programs: list[ProgramDef] = field(default_factory=list)
    data_types: list[DataTypeDef] = field(default_factory=list)


# ── Parser ────────────────────────────────────────────────────────────

class L5KParser:
    """Recursive descent parser for L5K text format."""

    def __init__(self, text: str):
        self.lines = text.splitlines()
        self.pos = 0
        self.controller = ControllerDef(name="Unknown")

    def parse(self) -> ControllerDef:
        while self.pos < len(self.lines):
            line = self.lines[self.pos].strip()
            self.pos += 1

            if line.startswith("IE_VER"):
                self.controller.ie_ver = self._extract_value(line, "IE_VER")
            elif line.startswith("CONTROLLER "):
                self._parse_controller_header(line)
                self._parse_controller_body()
        return self.controller

    def _parse_controller_header(self, line: str):
        m = re.match(
            r"CONTROLLER\s+(\S+)\s*\((.*)\)",
            line, re.DOTALL
        )
        if m:
            self.controller.name = m.group(1)
            params = self._parse_params(m.group(2))
            self.controller.processor_type = params.get("ProcessorType", "")
            self.controller.major = int(params.get("Major", 0))
            self.controller.minor = int(params.get("Minor", 0))

    def _parse_controller_body(self):
        while self.pos < len(self.lines):
            line = self.lines[self.pos].strip()
            self.pos += 1

            if line.startswith("END_CONTROLLER"):
                return
            elif line == "TAG":
                self.pos -= 1  # back up so _parse_tag_block sees the TAG line
                self._parse_tag_block("controller")
            elif line.startswith("PROGRAM "):
                self.pos -= 1
                self.controller.programs.append(self._parse_program(self.lines[self.pos].strip()))
            elif line.startswith("DATATYPE "):
                self.controller.data_types.append(self._parse_datatype(line))

    def _parse_tag_block(self, scope: str):
        """Parse TAG ... END_TAG block."""
        self.pos += 1  # skip TAG line
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            stripped = line.strip()

            if stripped == "END_TAG":
                self.pos += 1
                return

            if stripped and not stripped.startswith("//") and not stripped.startswith("(*"):
                tag = self._parse_tag_line(line, scope)
                if tag:
                    if scope == "controller":
                        self.controller.tags.append(tag)
                    # Program tags handled by caller

            self.pos += 1

    def _parse_tag_line(self, line: str, scope: str) -> Optional[TagDef]:
        """Parse a single tag definition line."""
        stripped = line.strip()
        # Skip description-only lines (indented)
        if not stripped or stripped.startswith("//"):
            return None

        # Tag format: name TYPE dimensions? (description?) Attributes? := value?
        m = re.match(
            r'(\w+(?:\[\d+(?:\.\.\d+)?(?:,\d+(?:\.\.\d+)?)?\])?)\s+'  # name
            r'(\w+(?:_\w+)*)\s*'  # type
            r'(.*)',  # rest
            stripped
        )
        if not m:
            return None

        name = m.group(1).strip("[]")
        tag_type = m.group(2)
        rest = m.group(3)

        # Check if it's an alias
        alias_match = re.search(r':=\s*(\S+)', rest)
        alias_for = alias_match.group(1) if alias_match else None

        tag = TagDef(
            name=name,
            tag_type="Alias" if alias_for else "Base",
            data_type=tag_type,
            alias_for=alias_for,
            scope=scope,
        )
        return tag

    def _parse_program(self, header_line: str) -> ProgramDef:
        m = re.match(r"PROGRAM\s+(\S+)\s*\(.*Class\s*:=\s*(\w+)", header_line)
        if not m:
            return ProgramDef(name="Unknown")

        prog = ProgramDef(name=m.group(1), program_class=m.group(2))

        self.pos += 1  # skip PROGRAM header
        while self.pos < len(self.lines):
            line = self.lines[self.pos].strip()

            if line == "END_PROGRAM":
                self.pos += 1
                return prog
            elif line == "TAG":
                self._parse_tag_block_in_program(prog)
            elif line.startswith("ROUTINE "):
                prog.routines.append(self._parse_routine(line))
            else:
                self.pos += 1

        return prog

    def _parse_tag_block_in_program(self, prog: ProgramDef):
        """Parse program-scope tags."""
        self.pos += 1  # skip TAG
        while self.pos < len(self.lines):
            line = self.lines[self.pos].strip()
            if line == "END_TAG":
                self.pos += 1
                return
            if line and not line.startswith("//"):
                tag = self._parse_tag_line(self.lines[self.pos], prog.name)
                if tag:
                    prog.tags.append(tag)
            self.pos += 1

    def _parse_routine(self, header_line: str) -> RoutineDef:
        m = re.match(r"ROUTINE\s+(\S+)\s*(?:\(.*Type\s*:=\s*(\w+))?", header_line)
        if m:
            return RoutineDef(name=m.group(1), language=m.group(2) or "Ladder")
        return RoutineDef(name=header_line.replace("ROUTINE ", "").strip())

    def _parse_datatype(self, header_line: str) -> DataTypeDef:
        return DataTypeDef(name=header_line.replace("DATATYPE ", "").strip(" ():"))

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_value(line: str, key: str) -> str:
        m = re.search(rf'{key}\s*:=\s*(\S+)', line)
        return m.group(1).strip(";\"") if m else ""

    @staticmethod
    def _parse_params(params_str: str) -> dict:
        """Parse key := value pairs."""
        result = {}
        for m in re.finditer(r'(\w+)\s*:=\s*("(?:[^"]*)"|\S+)', params_str):
            val = m.group(2).strip('"')
            result[m.group(1)] = val
        return result


def parse_l5k(path_or_text: str) -> ControllerDef:
    """Parse an L5K file path or text string into a ControllerDef."""
    if "\n" in path_or_text:
        text = path_or_text
    else:
        # Remove UTF-8 BOM if present
        with open(path_or_text, "r", encoding="utf-8-sig") as f:
            text = f.read()

    parser = L5KParser(text)
    return parser.parse()
