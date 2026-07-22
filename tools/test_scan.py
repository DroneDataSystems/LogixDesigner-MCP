"""Quick parser test — skip tag parsing."""
import sys, time
sys.path.insert(0, 'C:/projects/LogixDesigner-MCP/src')
from plc_parser.l5k import L5KParser

text = open(r'C:\temp\Palletizer.L5K', 'r', encoding='utf-8-sig').read()
parser = L5KParser(text)

# Just scan through lines — no parsing
start = time.time()
for i, line in enumerate(parser.lines):
    if i % 1000 == 0:
        elapsed = time.time() - start
        print(f"Line {i}: {line.strip()[:80] if line.strip() else '(empty)'}")
        if elapsed > 2:
            print(f"  (scanning... {i}/{len(parser.lines)})")
print(f"Total: {len(parser.lines)} lines in {time.time()-start:.1f}s")
