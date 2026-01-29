@echo off
REM ============================================================================
REM STL Creator - Stop All Services
REM ============================================================================

echo Stopping STL Creator services...

REM Stop by window title
taskkill /FI "WINDOWTITLE eq STL Creator Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq STL Creator Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq 3D Converter Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq 3D Converter Frontend*" /F >nul 2>&1

REM Stop by port (backup method)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1

echo All services stopped.
