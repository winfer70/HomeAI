#!/usr/bin/env bash
# jaskier was migrated from Windows 11 Pro to Ubuntu Server 26.04 LTS
# (2026-08-18), specifically to unblock this benchmark (Docker Desktop
# needed a GUI session on Windows). This is now the primary script for
# jaskier; benchmark_gpu_baseline.ps1 is kept only for reference.
#
# Note: `ollama run` needs a PTY when invoked over a non-interactive SSH
# session (e.g. from an automation tool) — use `ssh -tt`, or load the model
# via `curl .../api/generate` instead if a PTY isn't available.

set -euo pipefail

candidate_model="${1:-qwen2.5:7b-instruct}"

# When invoking remotely over SSH, allocate a PTY (`ssh -tt`) because
# `ollama run` may hang without one.

echo "=== GPU baseline: Frigate running, no LLM loaded ==="
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv

echo
echo "Pulling candidate model: ${candidate_model}"
ollama pull "${candidate_model}"

echo
echo "Loading model with a warm-up prompt..."
ollama run "${candidate_model}" "ping"

echo
echo "=== GPU with Frigate + model loaded ==="
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv
