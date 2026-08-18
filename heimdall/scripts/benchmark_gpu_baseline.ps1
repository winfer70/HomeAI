# NOTE: jaskier was migrated from Windows 11 Pro to Ubuntu Server 26.04 LTS
# (2026-08-18) specifically to unblock this benchmark. This PowerShell
# variant is now superseded by benchmark_gpu_baseline.sh for jaskier itself;
# kept only for reference or any future Windows host.

param(
    [string]$CandidateModel = "qwen2.5:7b-instruct"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# When invoking this script remotely over SSH, use `ssh -tt` so `ollama run`
# gets a PTY. The script itself assumes it is running locally on jaskier.

Write-Host "=== GPU baseline: Frigate running, no LLM loaded ==="
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv

Write-Host ""
Write-Host "Pulling candidate model: $CandidateModel"
ollama pull $CandidateModel

Write-Host ""
Write-Host "Loading model with a warm-up prompt..."
ollama run $CandidateModel "ping"

Write-Host ""
Write-Host "=== GPU with Frigate + model loaded ==="
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv
