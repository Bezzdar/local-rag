@echo off
set MODELPATH=models\wizardlm-13b-v1.2.Q4_K_M.gguf
set PORT=8003
set CTX_SIZE=4096
set N_GPU_LAYERS=0

cd /d "%~dp0"
llama.cpp\llama-server.exe -m %MODELPATH% --port %PORT% --ctx-size %CTX_SIZE% --n-gpu-layers %N_GPU_LAYERS%
pause
