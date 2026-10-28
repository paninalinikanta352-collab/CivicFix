@echo off
title CivicFix Launcher
echo ================================================
echo   CivicFix - starting both servers
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:3000
echo ================================================
echo.

start "CivicFix Backend :8000" cmd /k "cd /d %~dp0Backend\Backend && .venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"

timeout /t 2 >nul

start "CivicFix Frontend :3000" cmd /k "cd /d %~dp0frontend (2)\frontend && npm run dev"

echo Dono windows khul gayi hain:
echo   - Backend  : 8000   (band karne ke liye us window me Ctrl+C)
echo   - Frontend : 3000   (same)
echo.
echo Band karne ke liye yahan koi bhi key dabao (ye launcher band hoga, servers nahi).
pause >nul
