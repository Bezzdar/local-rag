@echo off
set MODELPATH=models\Meta-Llama-3-8B.Q4_K_M.gguf
set PORT=8001
set CTX_SIZE=4096
set N_GPU_LAYERS=0

cd /d "%~dp0"
llama.cpp\llama-server.exe -m %MODELPATH% --port %PORT% --ctx-size %CTX_SIZE% --n-gpu-layers %N_GPU_LAYERS%
pause
