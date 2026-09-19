@echo off
cd /d "%~dp0"
title ATC Symposium Desk
echo.
echo  ATC Symposium Desk — may co ma nguon
echo  Tool + model Whisper ATC + DB thu vien — ghi hoi thoai English
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\chay.ps1"
if errorlevel 1 (
  echo.
  echo  Loi. Doc dong tren roi bam phim bat ky de dong.
  pause >nul
)
