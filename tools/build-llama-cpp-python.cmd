@echo off
setlocal

set "VSDEVCMD=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
if not exist "%VSDEVCMD%" echo [ERROR] VsDevCmd not found: %VSDEVCMD% & exit /b 1

call "%VSDEVCMD%" -arch=x64 -host_arch=x64
if errorlevel 1 echo [ERROR] Failed to initialize MSVC environment. & exit /b 1

set "CMAKE_GENERATOR=Ninja"
set "FORCE_CMAKE=1"

echo [INFO] Using Python: F:\ATC-Symposium-Desk\.venv-llama-build\Scripts\python.exe
F:\ATC-Symposium-Desk\.venv-llama-build\Scripts\python.exe -m pip install --no-binary llama-cpp-python --force-reinstall llama-cpp-python
exit /b %errorlevel%
