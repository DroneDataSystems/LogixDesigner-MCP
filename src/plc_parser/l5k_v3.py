"""L5K Parser v3 — handles multi-line blocks."""
import re
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TagDef:
    name: str
    tag_type: str = "Base"
    data_type: str = "DINT"
    alias_for: Optional[str] = None
    scope: str = "controller"

@dataclass
class RoutineDef:
    name: str
    language: str = "Ladder"

@dataclass
class ProgramDef:
    name: str
    program_class: str = "Standard"
    routines: list[RoutineDef] = field(default_factory=list)
    tags: list[TagDef] = field(default_factory=list)

@dataclass
class ControllerDef:
    name: str
    processor_type: str = ""
    major: int = 0
    minor: int = 0
    ie_ver: str = "2.24"
    tags: list[TagDef] = field(default_factory=list)
    programs: list[ProgramDef] = field(default_factory=list)


def parse_l5k(text_or_path: str) -> ControllerDef:
    if "\n" in text_or_path:
        text = text_or_path
    else:
        with open(text_or_path, "r", encoding="utf-8-sig") as f:
            text = f.read()

    lines = text.splitlines()
    i = 0
    controller = ControllerDef(name="Unknown")

    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if line.startswith("IE_VER"):
            m = re.search(r"IE_VER\s*:=\s*([\d.]+)", line)
            if m:
                controller.ie_ver = m.group(1).strip(";")

        elif line.startswith("CONTROLLER "):
            # Accumulate multi-line header
            header = line
            paren_depth = header.count("(") - header.count(")")
            while paren_depth > 0 and i < len(lines):
                header += " " + lines[i].strip()
                paren_depth = header.count("(") - header.count(")")
                i += 1
            # Parse accumulated header
            m = re.match(r"CONTROLLER\s+(\S+)\s*\((.*)\)", header, re.DOTALL)
            if m:
                controller.name = m.group(1)
                params = m.group(2)
                for pm in re.finditer(r'(\w+)\s*:=\s*"([^"]*)"', params):
                    k, v = pm.group(1), pm.group(2)
                    if k == "ProcessorType":
                        controller.processor_type = v
                for pm in re.finditer(r"(\w+)\s*:=\s*(\d+)", params):
                    k, v = pm.group(1), int(pm.group(2))
                    if k == "Major":
                        controller.major = v
                    elif k == "Minor":
                        controller.minor = v

        elif line == "TAG":
            tags, i = _parse_tag_block(lines, i, "controller")
            controller.tags.extend(tags)

        elif line.startswith("PROGRAM "):
            prog, i = _parse_program(lines, i - 1)
            controller.programs.append(prog)

        elif line.startswith("END_CONTROLLER"):
            break

    return controller


def _parse_tag_block(lines: list[str], i: int, scope: str):
    """Parse TAG ... END_TAG, return (tags, new_index)."""
    tags = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        i += 1

        if stripped == "END_TAG":
            return tags, i
        if not stripped or stripped.startswith("//"):
            continue

        # Tag format variations:
        #   name TYPE (params...) := value;
        #   name OF alias_tag[member] (params...);
        #   name : TYPE[dim] (params...) := value;
        #   name : TYPE[dim] (params...);
        m = re.match(r'(\w+(?:\s*\[[^\]]+\])?)\s*(OF|:)?\s*(\w+)\s*(.*)', stripped)
        if not m:
            continue
        
        name = m.group(1).strip()
        is_alias = (m.group(2) == "OF")
        dtype = m.group(3) if not is_alias else "ALIAS"
        rest = m.group(4).strip()

        # Accumulate multi-line if rest has unmatched parens
        while rest.count("(") > rest.count(")") and i < len(lines):
            rest += " " + lines[i].strip()
            i += 1

        alias_for = None
        if is_alias:
            # "OF SomeTag[0] (params...)" — extract the alias target
            alias_m = re.match(r'(\w+(?:\[[^\]]*\])?)', rest)
            if alias_m:
                alias_for = alias_m.group(1)
        else:
            alias_m = re.search(r":=\s*(\S+)", rest)
            if alias_m:
                alias_for = alias_m.group(1).rstrip(";")

        tags.append(TagDef(
            name=name,
            data_type=dtype,
            tag_type="Alias" if (is_alias or alias_for) else "Base",
            alias_for=alias_for,
            scope=scope,
        ))

    return tags, i


def _parse_program(lines: list[str], i: int):
    """Parse PROGRAM ... END_PROGRAM, return (ProgramDef, new_index)."""
    header = lines[i].strip()
    i += 1

    # Accumulate multi-line header
    while header.count("(") > header.count(")") and i < len(lines):
        header += " " + lines[i].strip()
        i += 1

    m = re.match(r"PROGRAM\s+(\S+)\s*\(.*Class\s*:=\s*(\w+)", header)
    name = m.group(1) if m else header.split()[1] if len(header.split()) > 1 else "Unknown"
    pclass = m.group(2) if m else "Standard"
    prog = ProgramDef(name=name, program_class=pclass)

    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if line == "END_PROGRAM":
            return prog, i
        elif line == "TAG":
            tags, i = _parse_tag_block(lines, i, name)
            prog.tags.extend(tags)
        elif line.startswith("ROUTINE "):
            rm = re.match(r"ROUTINE\s+(\S+)", line)
            if rm:
                prog.routines.append(RoutineDef(
                    name=rm.group(1),
                    language="Ladder"
                ))

    return prog, i


if __name__ == "__main__":
    import sys, time
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\temp\Palletizer.L5K"
    start = time.time()
    c = parse_l5k(path)
    elapsed = time.time() - start
    print(f"Parsed in {elapsed:.2f}s")
    print(f"Controller: {c.name} v{c.major}.{c.minor} ({c.processor_type})")
    print(f"Tags: {len(c.tags)}")
    print(f"Programs: {len(c.programs)}")
    for p in c.programs:
        print(f"  {p.name}: {len(p.routines)} routines, {len(p.tags)} tags")
    if c.tags:
        print(f"First 5 tags:")
        for t in c.tags[:5]:
            a = f" -> {t.alias_for}" if t.alias_for else ""
            print(f"  {t.name}: {t.data_type}{a}")
