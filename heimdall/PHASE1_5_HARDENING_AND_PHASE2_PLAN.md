# Heimdall — Phase 1 Hardening & Phase 2 Plan

Phase 1 (M0–M6, plus the Task 8 memory add-on) is live and verified. This doc covers two
things: a backlog of gaps that surfaced *during* Phase 1 build-out and are worth closing
before adding more surface area, and a milestone plan for Phase 2 — the dedicated speaker
hardware, wake word, and voice-ID work the original design doc explicitly deferred.

---

## Part 1 — Hardening backlog (Phase 1.5)

Ordered by how much it'd hurt if left alone. None of these block Phase 2, but the first
three actively undermine work already done if left unaddressed.

### High priority

**1. vesemir's HA config isn't version-controlled — this is a real disaster-recovery gap.**
Every Heimdall-related `rest_command`/`script`/`rest:` sensor/custom component addition
lives only as live YAML on vesemir, with `HA_CONFIG_CHANGES.md` as prose documentation of
what changed. A vesemir wipe or corrupted install would mean manually replaying 9+ sections
of patch history by hand.

> **DONE (2026-08-20).** Recon found local `dev` had zero common ancestor with `origin/dev` —
> vesemir's clone was never re-synced after the 2026-08-15 `git-filter-repo` history rewrite
> (stale local tip 2026-07-26 vs. rewritten `origin/dev` tip 2026-08-15). Backed up the live
> `configuration.yaml`/`automations.yaml`, hard-reset local `dev` to `origin/dev`, branched
> `feature/heimdall-config-sync-20260820`, reapplied and committed the real drift (diff
> scanned clean for secrets first). Split Heimdall's `rest_command`/`script`/`rest`/
> `heimdall_llm_api` entries into a dedicated `heimdall.yaml`, merged back via HA's
> `packages` mechanism — validated clean with `check_config` (one unrelated, pre-existing
> `influxdb.include.component_config` schema bug found, not fixed, flagged separately).
> Deleted 49 ad hoc `.bak-*` files (incl. one with plaintext secrets) and gitignored the
> pattern. Pushed to origin: https://github.com/winfer70/ProjectNemo/pull/new/feature/heimdall-config-sync-20260820
> (PR still needs manual open+merge). **Action needed: rotate `heimdall_memory_token`,
> `influxdb_token`, and the Satel `alarm_code`** — briefly printed in plaintext to a terminal
> during config validation this session.

- Pull the actual `configuration.yaml` (or split Heimdall's additions into a dedicated
  `heimdall.yaml` included via `!include`) into git as the source of truth going forward,
  with the live file becoming the generated artifact instead of the other way around.
- At minimum, a scheduled backup script that snapshots `configuration.yaml` + `secrets.yaml`
  (redacted) off vesemir into the repo or a backup location.

**2. The Task 7 test matrix isn't scheduled — it only ran because someone invoked it.**
It caught two real regressions (the phantom Tuya entity, qwen's climate resolution) on its
very first run. That value only compounds if it keeps running. Needs a cron job / systemd
timer on jaskier, or a scheduled n8n workflow, running it daily-ish and routing failures to
the `heimdall-failures` ntfy topic that already exists.

**3. `ntfy_failure_logger.py` was written but never deployed as a running service.**
For the M6 "week of real usage, log every failure" goal to actually happen, this needs to
run continuously — a systemd service or a small container on jaskier — not be invoked
manually per-session like it was during testing.

### Medium priority

**4. The `kamilo-assistant` scoping question was never closed out.**
Flagged back at the start of the project (Task 3's cross-check) and never actually decided:
fold it into the local-model bake-off, or explicitly retire it.

> **Resolved (2026-08-20):** `kamilo-assistant` (jaskier, `qwen3:14b` Modelfile) is a
> general-purpose personal/homelab assistant with a broad system prompt covering all
> projects, trading rules, and infra — not a Home Assistant tool-calling agent, and has no
> tool schema at all. It solves a different problem than Heimdall (device control via
> Assist). **Decision: explicitly retire the fold-in idea** — the two stay separate
> assistants, no further action needed.

**5. GPU headroom hasn't been re-measured under real concurrent load.**
Task 1's benchmark was Frigate + one loaded 7B model. Since then: the bake-off winner is
loaded full-time, the memory-extraction poller periodically calls Ollama, and Frigate's
still running. Worth a fresh `nvidia-smi` snapshot during a busy moment before adding
wake-word processing on top, which will add its own (smaller but nonzero) load.

> **DONE (2026-08-20).** Idle baseline (qwen2.5:7b-instruct loaded, Frigate + memory poller
> running): 6328/12288 MiB VRAM used (5582 MiB free), 0% GPU utilization, 46°C, ~42W. Under
> an actual live inference burst (real `conversation.process` call to the qwen agent via HA):
> GPU utilization spiked to 98-100%, memory utilization to 100%, power draw peaked at ~170W
> (the 3060's rated TDP - i.e. compute-bound, not memory-bound, during a burst), 58°C, back
> down to idle within ~4 seconds of the response completing. VRAM **used** stayed flat at
> 6328 MiB throughout - inference on an already-loaded model doesn't need much extra memory
> beyond the resident weights + per-request KV cache. Conclusion: 5.5GB of free VRAM is
> comfortable headroom for M8's wake-word model (openWakeWord's models are tiny, low
> single-digit MB, INT8) - GPU compute contention during simultaneous wake-word + qwen
> inference is the more relevant risk than memory pressure, but wake-word inference is cheap
> enough continuously that it's unlikely to meaningfully compete with qwen's few-second
> bursts. No action needed before starting M8.

**6. qwen's two known limitations are documented, not fixed.**
`switch.office_led` name-ambiguity and the climate-entity alias not reaching qwen's tool
schema are both currently accepted as permanent weaknesses. Two real options instead of
"accepted forever": rename the ambiguous entities outright (aliases don't help qwen — direct
name clarity might), or have the n8n router's classifier route anything touching those two
entities to Gemini specifically.

**7. Guardrail coverage stops at the `heimdall/` git tree.**
Task 0's CI check only scans files under `heimdall/`. The actual dangerous action — an
`expose_entity` call reaching HA's live API — happens at runtime from scripts that talk to
HA directly, not from a file diff.

> **Resolved, already implemented.** `expose_entities.py` already calls
> `assert_no_alarm_entities()` (a domain-prefix check on `alarm_control_panel.`/`alarm.`) at
> the top of `main()`, before any WebSocket connection or API call is made — this is a
> runtime backstop, not just the CI file-scan. No other script in `heimdall/scripts/` calls
> `homeassistant/expose_entity`, so no other script needs this guard.

### Low priority

**8. Two loose ends already flagged, still open:**

- Stray "Gemini regression check" calendar event (2026-08-20) needs manual deletion — no
  `delete_event` service exists in this HA version.
  > **Still open, by design.** No automated `calendar.delete_event` service exists, and
  > extracting the Google OAuth refresh token out of HA's internal storage to call the
  > Calendar API directly was judged more risk than a one-off delete is worth. User will
  > delete it manually in Google Calendar's UI.
- The Google OAuth `client_secret_*.json` on the Desktop should move to a password manager
  or get deleted now that its contents are registered in HA.
  > **DONE (2026-08-20).** Deleted (`Kamil/client_secret_914645144271-....json`) — only the
  > app-level client_id/secret, already registered inside HA, not a live user token.

**9. Secrets handling during this build was ad hoc** — HA tokens and the n8n API key got
staged through `$env:TEMP` files per-session rather than a consistent local secrets store.
Worth consolidating into a single gitignored `.env.local` (or a proper secrets manager) that
every script reads from the same place.

> **DONE (2026-08-20).** Added `.env.local.example` (repo root, safe to commit) listing every
> var every `heimdall/scripts/*.py` and `test_matrix.py` already read via `os.environ.get`,
> plus `heimdall/scripts/Load-EnvLocal.ps1` to load a real `.env.local` (gitignored) into the
> current PowerShell session in one line (`. .\heimdall\scripts\Load-EnvLocal.ps1`). Migrated
> the existing ad hoc `$env:TEMP\ha_token.txt` into it and deleted the temp file. Also fixed
> `deploy_n8n_workflow.py`, which used bare `HA_TOKEN`/`HA_URL` instead of every other
> script's `HEIMDALL_HA_TOKEN`/`HEIMDALL_HA_URL` convention - renamed for consistency.

**10. `HA_CONFIG_CHANGES.md` is now 9+ sections and growing.** Fine for now; if Phase 2 adds
several more sections, consider splitting by integration (calendar / memory / aquarium /
test-matrix / voice-hardware) so it stays navigable.

---

## Part 2 — Phase 2: Dedicated Voice Hardware

Per the original implementation plan's explicit non-goals: *"No wake word, no
always-listening mic, no dedicated speaker hardware... no voice speaker identification (not
needed while every client is a personal, logged-in device)."* Phase 1 was a Companion App /
push-to-talk experience by design. Phase 2 is what changes that.

This is a bigger architectural shift than any single Phase 1 task — it introduces a device
that's always listening in shared physical space, not a personal phone someone consciously
opens. Worth treating the privacy/security implications as first-class, not an afterthought
bolted on at the end.

**Sequencing decision:** build the cheap, low-effort phone/watch improvements first (M7
below) using devices already owned, then take on the dedicated satellite build (M8 onward)
as a separate, later phase. They're not competing approaches — the phone/watch stage covers
personal hands-free control now; the satellite stage is what eventually gets you shared,
ambient, no-device-needed control in a room.

### M7 — Phone & watch quick-trigger (build this first)

**Objective:** get the fastest, cheapest improvement to personal hands-free control using
devices you already own, before spending on dedicated hardware. This won't give you shared
ambient control — see the tradeoff noted above — but it's near-zero cost and can ship
immediately.

**Deliverables:**

1. **Android:** confirm HA is set as the default assistant app (Settings → Apps → Default
   apps → Digital assistant app), triggered by the squeeze/long-press gesture — already
   partly verified working earlier in this project. Add a home-screen widget as a lighter
   one-tap alternative for when the gesture isn't convenient.
2. **iOS:** build a Siri Shortcut that calls the Home Assistant iOS Companion App's built-in
   Assist action. Realistically this won't be literally "Hey Siri, Heimdall" — Siri's
   custom-phrase support is limited — so land on something close like "Hey Siri, ask
   Heimdall" and confirm it reliably triggers the right pipeline.
3. **Apple Watch:** add the same Shortcut as a watch complication or via the Shortcuts app,
   so a single tap on the watch face starts listening.
4. Confirm each person's device defaults to their preferred language pipeline
   (`Heimdall-EN` / `Heimdall-PL`) — same per-device language binding that'll matter again
   for satellites in M8.
5. This one's mostly manual verification rather than something `test_matrix.py` can
   automate, since it's OS-level gesture/shortcut behavior, not an API call — worth a quick
   note in `TEST_MATRIX.md` that these rows are manually checked, not part of the automated
   suite.

**Acceptance criteria:** from a locked/idle phone or a watch face, starting Assist takes one
gesture or tap — no hunting through the Companion App's UI — confirmed working on both
Kamil's and Marzena's devices, in each person's default language.

### M8 — Wake word detection ("Heimdall", custom-trained)

**Decision locked in:** custom "Heimdall" wake word, not a generic pretrained one. More
build effort, but you get the actual product name — and jaskier's RTX 3060 (already running
Ollama) is more than enough GPU for training this, so it's not a new hardware cost, just
build time.

**Deliverables:**

1. Deploy `wyoming-openwakeword` on jaskier — same container pattern as the existing Wyoming
   STT/TTS services.
2. Train a custom "Heimdall" model via openWakeWord's automatic training pipeline: it
   synthesizes hundreds–thousands of "Heimdall" utterances across many TTS voices/accents,
   augments with background noise and simulated room acoustics, then trains a lightweight
   classifier — a couple hours on the 3060, no manual recording needed for the first pass.
   Once that baseline works, a few dozen real recordings each of Kamil and Marzena actually
   saying "Heimdall" naturally, fed back in as hard positives, will meaningfully improve
   real-world accuracy over synthetic-only.
3. Generate hard-negative training examples too — phrases that sound close to "Heimdall" in
   both English and Polish — so it doesn't false-trigger on nearby-sounding words in either
   language.
4. Wire the trained model into `wyoming-openwakeword`, then into the Assist pipeline as the
   trigger stage ahead of STT — confirm the exact pipeline-stage config against your live HA
   version before assuming it matches the docs, same caution that mattered for Assist
   pipelines back in Phase 1.
5. Extend `test_matrix.py` with wake-word rows: false-positive rate (silence/ambient
   noise/TV shouldn't trigger it), true-positive rate (does it reliably catch real "Heimdall"
   utterances), in both languages.

**Open architecture question worth deciding now, not after building:** HA's Assist pipeline
binds one language per pipeline — that's exactly why `Heimdall-EN` and `Heimdall-PL` exist as
two separate pipelines today (confirmed the hard way during Task 5). A wake-word satellite is
normally configured against a single default pipeline, not a per-utterance language switch.
Recommend for M8 v1: each physical satellite defaults to one primary language, matching
whoever's more often in that room, with manual pipeline switching as an accepted limitation.
True per-utterance auto-language-detection-then-routing is a real project on its own —
treating it as in-scope from day one would stall M8 for something orthogonal to getting the
wake word working at all.

**Acceptance criteria:** saying "Heimdall" from within earshot of the satellite starts a
listening window; ambient household noise (TV, conversation) doesn't false-trigger it more
than a handful of times a day.

### M9 — Dedicated satellite hardware

**Objective:** get a physical device in a room that's always listening for the wake word,
instead of relying on a phone.

**Decision locked in: Raspberry Pi over ESP32, for the first satellite.** Given M8's custom
wake word, this isn't a close call — but the reason is toolchain maturity, not reflash
cycles specifically (correcting something said imprecisely earlier): Pi satellites use
openWakeWord, ESP32 devices use a separate project called microWakeWord via ESPHome.
They're not the same pipeline. openWakeWord's custom-word training is more mature and better
documented; microWakeWord's is fiddlier to get a good custom word out of, independent of how
fast you can iterate. Validate the word on the more mature toolchain first — porting a
proven model to cheaper ESP32 hardware for multi-room scale-out is a reasonable second step
once the model's stable, not a first step.

**Deliverables:**

1. Raspberry Pi 4 or 5 + a USB mic/speaker array (a ReSpeaker 2-Mic HAT or similar far-field
   mic is the usual pairing) running `wyoming-satellite`.
2. Deploy this one pilot satellite in a single room first — don't roll out house-wide before
   M8's wake-word tuning is solid. Kitchen or living room are the obvious first picks given
   how much of the exposed entity list (lights, aquarium, gate) clusters around shared
   spaces.
3. Point it at jaskier's existing Wyoming STT/TTS endpoints and the primary-language
   pipeline decided for that room in M8 — no new voice-processing infrastructure needed,
   just a new client talking to what M1/M2 already built.
4. Physical mute control — most ReSpeaker HATs have a hardware button; wire it in if it's
   not on by default, given this is now an always-on mic in a shared room.

**Acceptance criteria:** wake word → command → response works end-to-end from the physical
device, in both languages, controlling at least one light and reading the aquarium temp
(reusing Task 3/4's existing exposed entities — no new entity work needed here).

### M10 — Speaker identification

**Objective:** once a satellite is shared hardware rather than a personal phone, "who's
asking" stops being implicit (whoever's logged into the Companion App) and needs to be
inferred from the voice itself — mainly so the memory system (Task 8) and personalized
calendar routing (Task 5's per-user default) still work correctly from a shared device.

**Deliverables:**

1. Voice-embedding service — same pattern as Task 8's memory service: a small FastAPI
   microservice on jaskier (`pyannote.audio` or `SpeechBrain` are the usual open-source
   choices), enrolling a short voice sample per household member.
2. Wire speaker-ID as a pre-processing step: satellite audio → speaker-ID service → inject
   "this is likely Kamil/Marzena" as context into the conversation request, the same way
   memory context already gets injected into the system prompt.
3. Explicit fallback behavior for "unrecognized speaker" (a guest, a TV) — should default to
   no personalization rather than guessing wrong.

**Acceptance criteria:** the system correctly attributes a calendar-write command to the
right person's calendar from the shared satellite, without the person having said their own
name.

**Privacy note:** voice embeddings for identifying specific family members are more
sensitive than voice commands generally — worth a deliberate retention/storage decision
here, not just reusing whatever pattern felt convenient for Task 8's fact store.

### M11 — Always-listening privacy & security hardening

**Objective:** close the gap between "Phase 1's privacy posture" (personal device,
push-to-talk) and "Phase 2's reality" (shared hardware, always listening for a wake word).

**Deliverables:**

1. Confirm the architecture genuinely keeps "only post-wake-word audio leaves the device" —
   this should be true by default with `wyoming-satellite`/ESPHome's design, but worth
   explicitly verifying rather than assuming, given how much of Phase 1 turned up
   assumptions that didn't hold under real testing.
2. Re-confirm the Satel alarm boundary holds regardless of trigger mechanism — Task 0's
   guardrail was built for a text/tool-call world; worth a specific check that
   wake-word-triggered voice can't reach anything the guardrail was meant to block.
3. Decide a retention policy for any audio clips that get logged for debugging or
   soak-testing — don't accumulate voice recordings indefinitely by default.

**Acceptance criteria:** written, explicit answers to "what audio ever leaves the device,"
"how long is anything retained," and "does the alarm boundary still hold" — not just
"presumably fine."

---

## Decisions locked in

- **Sequencing:** phone/watch improvements now (M7), dedicated satellite build later (M8
  onward) — not competing approaches, two different products serving different use cases.
- **Wake word:** custom "Heimdall," trained via openWakeWord on jaskier's existing GPU — not
  a generic pretrained word.
- **First satellite hardware:** Raspberry Pi + far-field USB mic, not ESP32 — chosen for
  openWakeWord's more mature custom-word toolchain versus ESP32's microWakeWord path; ESP32
  scale-out is a sensible follow-up once the model's proven, not the starting point.
- **kamilo-assistant scoping (backlog #4):** stays a separate, general-purpose assistant —
  not folded into Heimdall's tool-calling bake-off.

All three original hardware/sequencing decisions are reflected in M7–M9 above. The one thing
still worth a deliberate answer before M8 actually starts building is the per-satellite
language binding called out there — not a hardware/vendor choice, just a "which room
defaults to which language" decision that's cheap to make now and annoying to redo later.
