@echo off
REM ============================================================================
REM STL Creator - One-Click Installer
REM Sets up Python venv, installs dependencies, and seeds the database
REM ============================================================================

setlocal enabledelayedexpansion
set ROOT=%~dp0

echo.
echo  ============================================================
echo     STL Creator - First-Time Setup
echo  ============================================================
echo.

REM Check Python
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo    Found Python %PYTHON_VER%

REM Check Node.js
echo [2/6] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Node.js is not installed or not in PATH.
    echo Please install Node.js LTS from https://nodejs.org/
    echo.
    pause
    exit /b 1
)
for /f %%i in ('node --version 2^>^&1') do set NODE_VER=%%i
echo    Found Node.js %NODE_VER%

REM Create Python virtual environment
echo [3/6] Setting up Python virtual environment...
if not exist "%ROOT%venv" (
    python -m venv "%ROOT%venv"
    echo    Created new virtual environment
) else (
    echo    Virtual environment already exists
)

REM Install Python dependencies
echo [4/6] Installing Python dependencies...
"%ROOT%venv\Scripts\pip.exe" install --upgrade pip -q
"%ROOT%venv\Scripts\pip.exe" install -r "%ROOT%stl-generator\backend\requirements.txt" -q
echo    Dependencies installed

REM Install Node dependencies
echo [5/6] Installing Node.js dependencies...
cd /d "%ROOT%stl-generator\frontend"
call npm install --silent 2>nul
echo    Node modules installed

REM Create storage directories and seed database
echo [6/6] Initializing storage and database...
mkdir "%ROOT%storage\inputs" 2>nul
mkdir "%ROOT%storage\outputs" 2>nul
mkdir "%ROOT%storage\colmap_workspaces" 2>nul
mkdir "%ROOT%tools" 2>nul

cd /d "%ROOT%stl-generator\backend"
"%ROOT%venv\Scripts\python.exe" seed_db.py 2>nul
if errorlevel 1 (
    echo    Note: Database may already be seeded
) else (
    echo    Database seeded with defaults
)

echo.
echo  ============================================================
echo     Setup Complete!
echo  ============================================================
echo.
echo  To start the application, run:  start.bat
echo.
echo  Optional: To enable 3D scanning features, install:
echo    - COLMAP: https://colmap.github.io/install.html
echo    - OpenMVS: https://github.com/cdcseacave/openMVS
echo.
echo  Place tools in %ROOT%tools\ or set environment variables:
echo    - COLMAP_PATH
echo    - OPENMVS_PATH
echo.
pause
endlocal
