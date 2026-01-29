@echo off
setlocal

set PROJECT_ROOT=%~dp0
set BACKEND_DIR=%PROJECT_ROOT%stl-generator\backend
set FRONTEND_DIR=%PROJECT_ROOT%stl-generator\frontend

:MENU
cls
echo ==========================================================
echo      3D Printer Converter - Service Manager
echo ==========================================================
echo.
echo  1. Check Status
echo  2. Start Backend
echo  3. Start Frontend
echo  4. Restart All
echo  5. Stop All
echo  6. Exit
echo.
set /p choice="Select an option (1-6): "

if "%choice%"=="1" goto STATUS
if "%choice%"=="2" goto START_BACKEND
if "%choice%"=="3" goto START_FRONTEND
if "%choice%"=="4" goto RESTART_ALL
if "%choice%"=="5" goto STOP_ALL
if "%choice%"=="6" goto EXIT

goto MENU

:STATUS
echo.
echo Checking ports...
netstat -ano | findstr :8000 >nul && echo   Backend (Port 8000): RUNNING || echo   Backend (Port 8000): STOPPED
netstat -ano | findstr :3000 >nul && echo   Frontend (Port 3000): RUNNING || echo   Frontend (Port 3000): STOPPED
echo.
pause
goto MENU

:START_BACKEND
echo.
echo Starting Backend...
start "3D Converter Backend" cmd /k "cd /d %BACKEND_DIR% && %PROJECT_ROOT%venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
echo Backend started in new window.
pause
goto MENU

:START_FRONTEND
echo.
echo Starting Frontend...
start "3D Converter Frontend" cmd /k "cd /d %FRONTEND_DIR% && npm run dev"
echo Frontend started in new window.
pause
goto MENU

:STOP_ALL
echo.
echo Stopping services...
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
powershell -Command "Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
taskkill /FI "WINDOWTITLE eq 3D Converter Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq 3D Converter Frontend*" /F >nul 2>&1
echo Services stopped.
pause
goto MENU

:RESTART_ALL
echo.
echo Restarting all services...
call :STOP_ALL
timeout /t 2 >nul
call :START_BACKEND
timeout /t 2 >nul
call :START_FRONTEND
goto MENU

:EXIT
echo.
echo Goodbye!
endlocal
exit /b 0
