# Heimdall benchmarks

Measured 2026-08-18 on jaskier (192.168.0.125), **Ubuntu Server 26.04 LTS**,
RTX 3060 12GB, driver 595.84 / CUDA 13.2, Ollama 0.32.14, Frigate 0.17.2
(`stable-tensorrt`). jaskier was migrated from Windows 11 Pro to Linux
specifically to unblock this benchmark (Docker Desktop needed a GUI session,
Application Control blocked faster-whisper's `av` DLL, and the credential
helper needed DPAPI over an interactive session) — see
`../HANDOFF.md`/session history for the full migration writeup.

## GPU baseline

| State | GPU memory used | GPU memory total | GPU utilization | Notes |
| --- | --- | --- | --- | --- |
| Idle (Frigate stopped, no LLM) | 33 MiB | 12,288 MiB | 0% | |
| Frigate only | 1,133 MiB | 12,288 MiB | 19% | steady-state camera decode + detection |
| Frigate + LLM loaded | 5,794 MiB | 12,288 MiB | 2% | Candidate model: `qwen2.5:7b-instruct` (4.7GB, 100% GPU, 4096 ctx) |

### Headroom calculation

- Memory headroom after Frigate only: **11,155 MiB (~10.9 GB)**
- Memory headroom after Frigate + LLM loaded: **6,494 MiB (~6.3 GB)**
- Operational note: 12GB VRAM comfortably fits Frigate's NVR workload plus a
  7-8B instruct model simultaneously, with ~6GB free for context growth,
  concurrent STT/embedding load, or a slightly larger candidate model in the
  Task 3 bake-off. Larger candidates (e.g. 14B-class) should be re-checked
  against this same headroom before committing.

## STT latency

CPU-only (`device="cpu"`, `compute_type="int8"`), faster-whisper 1.2.1, run
via a local venv (`python3 -m venv`, no App Control/DPAPI issues on Linux —
`pip install faster-whisper` worked cleanly on the first try). All 4 clips
transcribed correctly in both languages at both model sizes.

### `medium` model

| Language | Filename | Latency (s) | Detected language | Transcribed text |
| --- | --- | --- | --- | --- |
| English | `en_light_command.wav` | 9.472 | en | Turn on the kitchen light. |
| English | `en_temperature_query.wav` | 8.350 | en | What is the temperature? |
| Polish | `pl_light_command.wav` | 8.522 | pl | Włącz światło w kuchni. |
| Polish | `pl_temperature_query.wav` | 8.357 | pl | Jaka jest temperatura? |

Average: **8.68s**

### `small` model

| Language | Filename | Latency (s) | Detected language | Transcribed text |
| --- | --- | --- | --- | --- |
| English | `en_light_command.wav` | 3.084 | en | Turn on the kitchen light. |
| English | `en_temperature_query.wav` | 2.758 | en | What is the temperature? |
| Polish | `pl_light_command.wav` | 2.858 | pl | Włącz światło w kuchni. |
| Polish | `pl_temperature_query.wav` | 2.789 | pl | Jaka jest temperatura? |

Average: **2.87s**

## Environment notes

- jaskier now runs **Ubuntu Server 26.04 LTS** (migrated from Windows 11 Pro
  specifically to unblock this benchmark — see migration history). Docker
  Engine (not Desktop), Ollama, and Frigate all run natively as Linux
  services/containers.
- Benchmark scripts run directly with the system `python3` (3.14.4) in a
  throwaway venv — no PowerShell, no App Control policy, no DPAPI-dependent
  credential helper.
- The synthetic Windows-SAPI-generated placeholder clips under
  `heimdall/tests/audio_samples/` were used as-is (both PL and EN transcribed
  perfectly at both model sizes) — they are still not representative of real
  accented/noisy speech. **Recommend replacing with real human-recorded
  clips before Task 3's bake-off** to validate this decision holds for
  natural speech, not just clean synthetic TTS audio.

## Go/no-go decision: `medium` vs `small`

**Decision: use `small` for Heimdall's Wyoming STT container (Task 2).**

Decision notes:

- `small` latency: **2.87s average** (2.76–3.08s range)
- `medium` latency: **8.68s average** (8.35–9.47s range) — ~3x slower
- Accuracy trade-off summary: on this test set (4 short command/query
  phrases, PL + EN), **both models transcribed every clip correctly** with
  correct language detection — no accuracy difference observed. This is a
  small, clean, synthetic-speech sample, so the accuracy comparison should be
  treated as inconclusive rather than a guarantee `small` matches `medium`'s
  accuracy on real-world noisy/accented audio.
- Final recommendation: ship `small` first — for a voice assistant, ~2.9s
  vs ~8.7s per-utterance latency is the difference between "usable" and
  "frustrating," and nothing in this test set shows a `small` accuracy
  penalty. Re-run this comparison once real human-recorded PL/EN clips
  (including accented/imperfect speech) are available, and fall back to
  `medium` only if `small`'s real-world accuracy proves unacceptable in
  practice during Task 2/3 testing.
