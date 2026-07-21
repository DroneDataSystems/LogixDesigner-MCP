"""Discover Logix Designer SDK COM interfaces on this machine."""
import sys
import os

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pythonnet
pythonnet.load('netfx')
import clr
import comtypes.client
import winreg


def try_progids():
    """Attempt to create COM objects via known ProgIDs."""
    progids = [
        'LdSdkServer.Application',
        'LogixDesignerSDK.Application',
        'RaLdSdk.Application',
        'LogixDesigner.Application',
        'LdSdkServer.SdkServer',
        'LdSdkServer.Service',
        'LdSdkServer.Server',
    ]
    for pid in progids:
        try:
            obj = comtypes.client.CreateObject(pid)
            members = [m for m in dir(obj) if not m.startswith('_')]
            print(f'SUCCESS: ProgID = {pid}')
            print(f'  Type: {type(obj).__name__}')
            print(f'  Members ({len(members)}): {members[:30]}')
            return obj, pid
        except Exception as e:
            print(f'  FAIL: {pid} -> {e}')
    return None, None


def scan_registry():
    """Scan COM registry for Logix/LdSdk classes."""
    print('\nScanning HKLM\\SOFTWARE\\Classes\\CLSID (first 2000 keys)...')
    count = 0
    found = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Classes\CLSID') as clsid_key:
            for i in range(2000):
                try:
                    key_name = winreg.EnumKey(clsid_key, i)
                    with winreg.OpenKey(clsid_key, key_name) as sub:
                        try:
                            name, _ = winreg.QueryValueEx(sub, '')
                            if name and any(x in name.lower() for x in ('logix', 'ldsdk', 'ralogix', 'ra.logix')):
                                found.append((key_name, name))
                                count += 1
                                if count <= 20:
                                    print(f'  {key_name}: {name}')
                        except:
                            pass
                except OSError:
                    break
    except Exception as e:
        print(f'  Registry scan error: {e}')
    
    if len(found) > 20:
        print(f'  ... and {len(found) - 20} more matches')
    print(f'  Total matches: {len(found)}')


def inspect_typelib(path):
    """Try to load a typelib from the SDK DLL."""
    print(f'\nInspecting type library for: {path}')
    try:
        from comtypes import typeinfo
        from comtypes.client import GetModule
        GetModule(path)
        print('  Type library loaded successfully')
    except Exception as e:
        print(f'  Type lib load failed: {e}')


if __name__ == '__main__':
    sdk_path = r'C:\Program Files (x86)\Rockwell Software\Studio 5000\Logix Designer SDK\LdSdkServer.dll'
    
    print('=== Step 1: Try ProgIDs ===')
    obj, pid = try_progids()
    
    print('\n=== Step 2: Scan COM Registry ===')
    scan_registry()
    
    print('\n=== Step 3: Try Type Library ===')
    inspect_typelib(sdk_path)
    
    if obj:
        print(f'\n=== Found working ProgID: {pid} ===')
        print('Ready to map methods to MCP tools.')
