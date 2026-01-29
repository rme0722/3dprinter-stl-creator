@echo off
REM ============================================================================
REM STL Creator - Quick Start
REM Starts backend and frontend servers and opens browser
REM ============================================================================

setlocal
set ROOT=%~dp0

echo.
echo Starting STL Creator...
echo.

REM Check if venv exists
if not exist "%ROOT%venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Please run install.bat first to set up the application.
    pause
    exit /b 1
)

REM Start backend server
echo Starting backend server...
start "STL Creator Backend" cmd /c "cd /d %ROOT%stl-generator\backend && %ROOT%venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

REM Wait for backend to start
echo Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

REM Start frontend server
echo Starting frontend server...
start "STL Creator Frontend" cmd /c "cd /d %ROOT%stl-generator\frontend && npm run dev"

REM Wait for frontend to start
echo Waiting for frontend to initialize...
timeout /t 5 /nobreak >nul

REM Open browser
echo Opening browser...
start http://localhost:3000

echo.
echo  ============================================================
echo     STL Creator is Running!
echo  ============================================================
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo.
echo   To stop the application, close this window or run stop.bat
echo.
echo Press any key to stop all services...
pause >nul

echo.
echo Stopping services...
taskkill /FI "WINDOWTITLE eq STL Creator Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq STL Creator Frontend*" /F >nul 2>&1

REM Also kill by port as backup
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1

echo Done!
endlocal
