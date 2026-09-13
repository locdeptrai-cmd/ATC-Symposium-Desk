@echo off
cd /d "%~dp0"
title ATC Symposium Desk — dong goi
echo.
echo  Dong goi EXE (kem DB) + APK Android vao phat-hanh\
echo  iOS native van can Mac + Xcode.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\dong-goi-phat-hanh.ps1"
if errorlevel 1 (
  echo.
  echo  Loi. Doc dong tren roi bam phim bat ky de dong.
  pause >nul
  exit /b 1
)
echo.
echo  Xong. Bam phim bat ky de dong.
pause >nul
