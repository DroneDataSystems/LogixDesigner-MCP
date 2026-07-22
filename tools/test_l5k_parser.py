"""Test L5K parser against the Palletizer export."""
import sys
sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/src')
from plc_parser import parse_l5k

l5k_path = r"C:\temp\Palletizer.L5K"

print(f"Parsing {l5k_path}...")
controller = parse_l5k(l5k_path)

print(f"\nController: {controller.name}")
print(f"  Processor: {controller.processor_type}")
print(f"  Revision: v{controller.major}.{controller.minor}")
print(f"  IE_VER: {controller.ie_ver}")
print(f"  Controller tags: {len(controller.tags)}")
print(f"  Programs: {len(controller.programs)}")
print(f"  Data types: {len(controller.data_types)}")

print(f"\nPrograms:")
for p in controller.programs:
    print(f"  {p.name} ({p.program_class}): {len(p.routines)} routines, {len(p.tags)} tags")
    for r in p.routines:
        print(f"    - {r.name} ({r.language})")

print(f"\nSample controller tags:")
for t in controller.tags[:10]:
    print(f"  {t.name}: {t.data_type} {'-> ' + t.alias_for if t.alias_for else ''}")
