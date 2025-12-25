@echo off
REM ============================================================================
REM STL Creator Build Script
REM Packages the application for distribution
REM ============================================================================

setlocal enabledelayedexpansion

set BUILD_DIR=dist\STL-Creator
set PYTHON_EMBED_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
set NODE_URL=https://nodejs.org/dist/v20.10.0/node-v20.10.0-win-x64.zip

echo ============================================
echo STL Creator Build Script
echo ============================================

REM Create distribution directory
if exist dist rmdir /s /q dist
mkdir %BUILD_DIR%

echo.
echo [1/7] Downloading embedded Python...
powershell -Command "Invoke-WebRequest -Uri '%PYTHON_EMBED_URL%' -OutFile 'python-embed.zip'"
powershell -Command "Expand-Archive -Path 'python-embed.zip' -DestinationPath '%BUILD_DIR%\python' -Force"
del python-embed.zip

echo.
echo [2/7] Setting up Python packages...
REM Copy site-packages from venv
xcopy /E /I /Y "..\..\venv\Lib\site-packages" "%BUILD_DIR%\python\Lib\site-packages"

REM Enable site-packages in embedded Python
echo import site >> %BUILD_DIR%\python\python311._pth

echo.
echo [3/7] Copying backend application...
xcopy /E /I /Y "app" "%BUILD_DIR%\backend\app"
copy requirements.txt "%BUILD_DIR%\backend\"

echo.
echo [4/7] Copying frontend standalone build...
xcopy /E /I /Y "..\frontend\.next\standalone" "%BUILD_DIR%\frontend"
xcopy /E /I /Y "..\frontend\.next\static" "%BUILD_DIR%\frontend\.next\static"
xcopy /E /I /Y "..\frontend\public" "%BUILD_DIR%\frontend\public"

echo.
echo [5/7] Downloading Node.js...
powershell -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile 'node.zip'"
powershell -Command "Expand-Archive -Path 'node.zip' -DestinationPath 'temp-node' -Force"
move temp-node\node-* %BUILD_DIR%\node
rmdir temp-node
del node.zip

echo.
echo [6/7] Copying COLMAP and OpenMVS...
xcopy /E /I /Y "C:\Tools\COLMAP" "%BUILD_DIR%\tools\COLMAP"
xcopy /E /I /Y "C:\Tools\OpenMVS" "%BUILD_DIR%\tools\OpenMVS"

echo.
echo [7/7] Creating launcher scripts...

REM Create main launcher
(
echo @echo off
echo setlocal
echo set ROOT=%%~dp0
echo set PATH=%%ROOT%%python;%%ROOT%%node;%%ROOT%%tools\COLMAP;%%ROOT%%tools\OpenMVS;%%PATH%%
echo.
echo echo Starting STL Creator...
echo echo.
echo echo Backend: http://localhost:8000
echo echo Frontend: http://localhost:3000
echo echo.
echo.
echo start "Backend" /D "%%ROOT%%backend" "%%ROOT%%python\python.exe" -m uvicorn app.main:app --port 8000
echo timeout /t 3 /nobreak ^>nul
echo start "Frontend" /D "%%ROOT%%frontend" "%%ROOT%%node\node.exe" server.js
echo timeout /t 2 /nobreak ^>nul
echo start http://localhost:3000
echo.
echo echo.
echo echo STL Creator is running!
echo echo Close this window to stop the application.
echo pause
) > %BUILD_DIR%\Start-STL-Creator.bat

REM Create stop script
(
echo @echo off
echo echo Stopping STL Creator...
echo taskkill /F /IM python.exe 2^>nul
echo taskkill /F /IM node.exe 2^>nul
echo echo Done.
) > %BUILD_DIR%\Stop-STL-Creator.bat

echo.
echo ============================================
echo Build Complete!
echo Output: %BUILD_DIR%
echo ============================================
echo.
echo To create installer, run Inno Setup with installer.iss

endlocal
