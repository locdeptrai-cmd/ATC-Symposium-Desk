@echo off
setlocal
cd /d "%~dp0.."

set "PY=F:\ATC-Symposium-Desk\.venv-gemma-local\Scripts\python.exe"
set "MODEL=D:\models\google\gemma-4-E4B-it-qat-q4_0-gguf\gemma-4-E4B_q4_0-it.gguf"

if not exist "%PY%" (
  echo [ERROR] Python venv not found: %PY%
  echo Run setup first to create .venv-gemma-local.
  exit /b 1
)

if not exist "%MODEL%" (
  echo [ERROR] GGUF model not found: %MODEL%
  exit /b 1
)

echo Starting llama.cpp OpenAI server on http://127.0.0.1:8012/v1
echo Model: %MODEL%
echo Press Ctrl+C to stop.

set "LLAMA_ARG_THREADS=8"
set "LLAMA_ARG_CTX=1024"

"%PY%" -m llama_cpp.server ^
  --host 127.0.0.1 ^
  --port 8012 ^
  --model "%MODEL%" ^
  --chat_format gemma ^
  --n_ctx %LLAMA_ARG_CTX% ^
  --n_threads %LLAMA_ARG_THREADS% ^
  --n_gpu_layers 0
