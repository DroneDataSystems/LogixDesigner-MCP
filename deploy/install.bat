@echo off
setlocal EnableDelayedExpansion
REM ============================================================================
REM Logix MCP Server - Windows Installation Script
REM ============================================================================
REM Run this from the root of the cloned logix-mcp repository on the Windows
REM machine where Studio 5000 is installed.
REM
REM Prerequisites:
REM   - Windows Server 2022 (or Windows 10/11)
REM   - Studio 5000 v33+ installed
REM   - Python 3.11+ installed and in PATH
REM   - Git installed (to clone this repo)
REM
REM Usage:
REM   cd C:\path\to\logix-mcp
REM   deploy\install.bat
REM ============================================================================

echo.
echo ============================================================
echo   Logix MCP Server - Windows Installation
echo ============================================================
echo.

REM --------------------------------------------------------------------------
REM 1. Check Python version (3.11+ required)
REM --------------------------------------------------------------------------
echo [1/6] Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.11+ from https://python.org and ensure "Add to PATH" is checked.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Found Python %PYVER%

REM Extract major/minor for comparison
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)

if %PYMAJOR% LSS 3 (
    echo ERROR: Python 3.11+ required, found %PYVER%
    pause
    exit /b 1
)
if %PYMAJOR% EQU 3 if %PYMINOR% LSS 11 (
    echo ERROR: Python 3.11+ required, found %PYVER%
    pause
    exit /b 1
)
echo Python version OK.
echo.

REM --------------------------------------------------------------------------
REM 2. Create virtual environment
REM --------------------------------------------------------------------------
echo [2/6] Creating Python virtual environment...
if exist .venv (
    echo Virtual environment already exists at .venv
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Created .venv
)
echo.

REM --------------------------------------------------------------------------
REM 3. Install project and dependencies
REM --------------------------------------------------------------------------
echo [3/6] Installing logix-mcp package and dependencies...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Upgrade pip first
python -m pip install --upgrade pip

REM Install the project in editable mode (assumes pyproject.toml exists)
pip install -e .
if errorlevel 1 (
    echo ERROR: pip install failed.
    echo Check that you are running from the repository root containing pyproject.toml.
    pause
    exit /b 1
)
echo Installation complete.
echo.

REM --------------------------------------------------------------------------
REM 4. Discover Logix Designer SDK assembly
REM --------------------------------------------------------------------------
echo [4/6] Discovering Logix Designer SDK assembly...
set SDK_FOUND=0
set SDK_PATH=

REM Common Studio 5000 installation paths (v33+)
set "STUDIO_BASE=C:\Program Files (x86)\Rockwell Software\Studio 5000"
set "STUDIO_BASE2=C:\Program Files\Rockwell Software\Studio 5000"

REM Try to find LogixDesigner.SDK.dll or similar SDK assembly
for %%p in (
    "%STUDIO_BASE%\LogixDesigner.SDK.dll"
    "%STUDIO_BASE%\Bin\LogixDesigner.SDK.dll"
    "%STUDIO_BASE%\SDK\LogixDesigner.SDK.dll"
    "%STUDIO_BASE%\RALogixDesignerSDK.dll"
    "%STUDIO_BASE%\Bin\RALogixDesignerSDK.dll"
    "%STUDIO_BASE2%\LogixDesigner.SDK.dll"
    "%STUDIO_BASE2%\Bin\LogixDesigner.SDK.dll"
) do (
    if exist "%%~p" (
        set "SDK_PATH=%%~p"
        set SDK_FOUND=1
        goto :sdk_found
    )
)

REM If not found in common paths, search recursively (limited depth)
if %SDK_FOUND% EQU 0 (
    echo Searching Studio 5000 directories...
    for /f "delims=" %%f in ('dir /s /b "%STUDIO_BASE%\*SDK*.dll" 2^>nul') do (
        set "SDK_PATH=%%f"
        set SDK_FOUND=1
        goto :sdk_found
    )
    for /f "delims=" %%f in ('dir /s /b "%STUDIO_BASE2%\*SDK*.dll" 2^>nul') do (
        set "SDK_PATH=%%f"
        set SDK_FOUND=1
        goto :sdk_found
    )
)

:sdk_found
if %SDK_FOUND% EQU 1 (
    echo Found SDK assembly: %SDK_PATH%
    echo.
    echo Set this path in your environment or config:
    echo   set LOGIX_SDK_ASSEMBLY=%SDK_PATH%
) else (
    echo WARNING: Could not automatically locate Logix Designer SDK assembly.
    echo Please manually locate the SDK DLL under your Studio 5000 installation.
    echo Typical location: C:\Program Files (x86)\Rockwell Software\Studio 5000\
    echo.
    echo Once found, set the environment variable:
    echo   set LOGIX_SDK_ASSEMBLY=C:\path\to\LogixDesigner.SDK.dll
)
echo.

REM --------------------------------------------------------------------------
REM 5. Verify pythonnet can load CLR (if SDK found)
REM --------------------------------------------------------------------------
echo [5/6] Testing pythonnet CLR load...
python -c "import clr; print('pythonnet OK: CLR loaded successfully')" 2>nul
if errorlevel 1 (
    echo WARNING: pythonnet test failed. This may indicate:
    echo   - pythonnet is not installed correctly
    echo   - .NET Framework 4.x runtime is missing
    echo   - Visual C++ Redistributable is missing
    echo.
    echo Install .NET Framework 4.8 and VC++ 2015-2022 Redistributable x64.
) else (
    echo pythonnet CLR load successful.
)
echo.

REM --------------------------------------------------------------------------
REM 6. Print next steps
REM --------------------------------------------------------------------------
echo [6/6] Installation complete! Next steps:
echo.
echo ============================================================
echo   CONFIGURATION
echo ============================================================
echo.
echo 1. Set the authentication token (required for remote access):
echo.
echo    setx LOGIX_MCP_TOKEN "your-secret-token-here"
echo.
echo    Generate a strong token, e.g.:
echo    python -c "import secrets; print(secrets.token_urlsafe(32))"
echo.
echo 2. (Optional) Set SDK assembly path if not auto-discovered:
echo.
echo    setx LOGIX_SDK_ASSEMBLY "C:\path\to\LogixDesigner.SDK.dll"
echo.
echo ============================================================
echo   STARTING THE SERVER
echo ============================================================
echo.
echo From the repository root:
echo.
echo    .venv\Scripts\activate
echo    fastmcp run src\logix_mcp\server.py:create_app --transport sse --host 127.0.0.1 --port 8765
echo.
echo Or using python -m:
echo.
echo    .venv\Scripts\python -m fastmcp run src\logix_mcp\server.py:create_app --transport sse --host 127.0.0.1 --port 8765
echo.
echo ============================================================
echo   CLOUDFLARE TUNNEL (for remote access)
echo ============================================================
echo.
echo See deploy\cloudflared-config.yml for tunnel setup instructions.
echo Quick summary:
echo    cloudflared tunnel create logix-mcp
echo    cloudflared tunnel route dns logix-mcp logix-mcp.your-domain.com
echo    cloudflared service install
echo.
echo ============================================================
echo   HERMES CLIENT CONFIG
echo ============================================================
echo.
echo See deploy\hermes-config.yaml for the Hermes MCP client snippet
echo to merge into ~/.hermes/config.yaml on your Linux machine.
echo.
echo ============================================================
echo.

pause
endlocal
