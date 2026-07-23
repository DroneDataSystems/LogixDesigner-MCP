"""L5K Parser v4 — proper tag handling with multi-line attributes."""
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
            header = _accumulate_header(lines, i - 1)
            i = header[1]
            m = re.match(r"CONTROLLER\s+(\S+)\s*\((.*)\)", header[0], re.DOTALL)
            if m:
                controller.name = m.group(1)
                for pm in re.finditer(r'(\w+)\s*:=\s*"([^"]*)"', m.group(2)):
                    if pm.group(1) == "ProcessorType":
                        controller.processor_type = pm.group(2)
                for pm in re.finditer(r"(\w+)\s*:=\s*(\d+)", m.group(2)):
                    if pm.group(1) == "Major":
                        controller.major = int(pm.group(2))
                    elif pm.group(1) == "Minor":
                        controller.minor = int(pm.group(2))

        elif line == "TAG":
            tags, i = _parse_tag_block(lines, i, "controller")
            controller.tags.extend(tags)

        elif line.startswith("PROGRAM "):
            prog, i = _parse_program(lines, i - 1)
            controller.programs.append(prog)

        elif line.startswith("END_CONTROLLER"):
            break

    return controller


def _accumulate_header(lines, start):
    """Accumulate multi-line header until parens match."""
    header = lines[start].strip()
    i = start + 1
    depth = header.count("(") - header.count(")")
    while depth > 0 and i < len(lines):
        header += " " + lines[i].strip()
        depth = header.count("(") - header.count(")")
        i += 1
    return header, i


def _parse_tag_block(lines, i, scope):
    """Parse TAG ... END_TAG. Tags start with \\t\\t (two tabs)."""
    tags = []
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        i += 1

        if stripped == "END_TAG":
            return tags, i
        if not stripped or stripped.startswith("//"):
            continue

        # A tag starts with \\t\\t (indent level 2) and a word
        if raw.startswith("\t\t") and not raw.startswith("\t\t\t"):
            tag, i = _parse_one_tag(lines, i - 1, scope)
            if tag:
                tags.append(tag)

    return tags, i


def _parse_one_tag(lines, start, scope):
    """Parse a single tag that may span multiple lines."""
    raw = lines[start]
    stripped = raw.strip()
    i = start + 1

    # Accumulate multi-line tag body until next tag or END_TAG
    body = stripped
    while i < len(lines):
        next_raw = lines[i]
        next_stripped = next_raw.strip()
        # Stop at next tag, END_TAG, PROGRAM, or END_CONTROLLER
        if (next_raw.startswith("\t\t") and not next_raw.startswith("\t\t\t")) or \
           next_stripped in ("END_TAG", "END_CONTROLLER") or \
           next_stripped.startswith("PROGRAM "):
            break
        # Accumulate attribute lines (indented with 3+ tabs)
        if next_raw.startswith("\t\t\t") or next_raw.startswith("\t\t  "):
            body += " " + next_stripped
        i += 1

    # Parse the accumulated body
    return _parse_tag_body(body, scope), i


def _parse_tag_body(body: str, scope: str):
    """Parse tag body: NAME : TYPE[dim] (params...) := value;"""
    # Match: NAME : TYPE (params...) := value;
    # or:    NAME OF AliasTag (params...);
    m = re.match(r'(\w+)\s+(OF|:)\s+(\w+(?:\[[^\]]*\])?)\s*(.*)', body)
    if not m:
        return None

    name = m.group(1)
    is_alias = (m.group(2) == "OF")
    dtype = m.group(3) if not is_alias else "ALIAS"
    rest = m.group(4).strip()

    alias_for = None
    tag_type = "Base"
    
    if is_alias:
        # True alias: name OF SomeTag[0] (...)
        # The alias target is in the dtype field (e.g., "Pal2_N35[0]")
        alias_for = dtype
        dtype = "ALIAS"
        tag_type = "Alias"
    else:
        # Base tag with optional initial value: name : TYPE (attrs...) := value;
        # Match the final := value (not Description :=, Class :=, etc.)
        m = re.search(r":=\s*([^\"].+?)\s*;?\s*$", rest)
        if m:
            alias_for = m.group(1).strip().rstrip(";")
        # Don't set tag_type = Alias for base tags with initial values

    return TagDef(
        name=name,
        data_type=dtype,
        tag_type=tag_type,
        alias_for=alias_for,
        scope=scope,
    )


def _parse_program(lines, i):
    """Parse PROGRAM ... END_PROGRAM."""
    header, i = _accumulate_header(lines, i)
    m = re.match(r"PROGRAM\s+(\S+)\s*\(.*Class\s*:=\s*(\w+)", header)
    name = m.group(1) if m else header.split()[1] if len(header.split()) > 1 else "Unknown"
    pclass = m.group(2) if m else "Standard"
    prog = ProgramDef(name=name, program_class=pclass)

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        i += 1

        if stripped == "END_PROGRAM":
            return prog, i
        elif stripped == "TAG":
            tags, i = _parse_tag_block(lines, i, name)
            prog.tags.extend(tags)
        elif stripped.startswith("ROUTINE "):
            rm = re.match(r"ROUTINE\s+(\S+)", stripped)
            if rm:
                prog.routines.append(RoutineDef(name=rm.group(1)))

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
        print(f"First 10 tags:")
        for t in c.tags[:10]:
            a = f" -> {t.alias_for[:50]}" if t.alias_for else ""
            print(f"  {t.name}: {t.data_type}{a}")
