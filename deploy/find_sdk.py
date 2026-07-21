"""Discover the Logix Designer SDK assembly on this Windows machine.

Prints the full path of the first found SDK DLL to stdout, or nothing if not found.
Called by deploy/install.bat — run from the repo root.
"""
import sys
import os
import glob

KNOWN = [
    r"C:\Program Files (x86)\Rockwell Software\Studio 5000\LogixDesigner.SDK.dll",
    r"C:\Program Files (x86)\Rockwell Software\Studio 5000\Bin\LogixDesigner.SDK.dll",
    r"C:\Program Files (x86)\Rockwell Software\Studio 5000\SDK\LogixDesigner.SDK.dll",
    r"C:\Program Files (x86)\Rockwell Software\Studio 5000\RALogixDesignerSDK.dll",
    r"C:\Program Files (x86)\Rockwell Software\Studio 5000\Bin\RALogixDesignerSDK.dll",
    r"C:\Program Files\Rockwell Software\Studio 5000\LogixDesigner.SDK.dll",
    r"C:\Program Files\Rockwell Software\Studio 5000\Bin\LogixDesigner.SDK.dll",
]

# Check known exact paths first
for p in KNOWN:
    if os.path.exists(p):
        print(p)
        sys.exit(0)

# Fall back to recursive search
BASES = [
    r"C:\Program Files (x86)\Rockwell Software\Studio 5000",
    r"C:\Program Files\Rockwell Software\Studio 5000",
]

for base in BASES:
    if os.path.isdir(base):
        hits = glob.glob(os.path.join(base, "**", "*SDK*.dll"), recursive=True)
        if hits:
            print(hits[0])
            sys.exit(0)
