# HANDOFF — HomeAI
Date: 2026-08-20

## Heimdall Phase 1.5 & Phase 2 planning (this session, latest)
- Locked in a full plan: `heimdall/PHASE1_5_HARDENING_AND_PHASE2_PLAN.md` — a 10-item
  hardening backlog (Phase 1.5) plus milestones M7-M11 (Phase 2: phone/watch quick-trigger,
  custom wake word, satellite hardware, speaker-ID, privacy hardening).
- Recon confirmed backlog #1 concretely: vesemir's `homeassistant/config/configuration.yaml`
  + `automations.yaml` (tracked in ProjectNemo repo, `dev` branch) have uncommitted local
  changes since 2026-06-07 — every Heimdall-era config edit (Tasks 0-8) was never committed.
  40+ untracked `.bak-*` files also present in the config dir.
- Backlog #4 (kamilo-assistant scoping) resolved: it's a separate general-purpose assistant,
  not folded into Heimdall — no code change needed.
- Backlog #7 (runtime guardrail) confirmed already implemented: `expose_entities.py` calls
  `assert_no_alarm_entities()` before any HA API call, not just relying on Task 0's CI scan.
- **Still open, needs user decision before executing:** how to handle vesemir's config drift
  (commit as-is / split into `heimdall.yaml` via `!include` first / what to do with the
  `.bak-*` pile) — this touches live production HA config, so it's not something to just do
  without a go-ahead.
- Exposed OAuth secret (`Kamil/client_secret_914645144271-....json` on Desktop root) still
  present — flagged, not yet deleted/moved pending user confirmation.

## Backlog #1 executed (same session, later)
- vesemir's ProjectNemo clone was stale/orphaned since the 2026-08-15 `git-filter-repo`
  rewrite (zero common ancestor with `origin/dev`, last real local commit 2026-07-26).
  Backed up live config, reset local `dev` to `origin/dev`, branched
  `feature/heimdall-config-sync-20260820`, committed the real Heimdall config drift (diff
  scanned clean for secrets), split Heimdall's `rest_command`/`script`/`rest`/
  `heimdall_llm_api` entries into `heimdall.yaml` via HA's `packages` mechanism, validated
  with `check_config` (clean, except one unrelated pre-existing `influxdb.include.
  component_config` schema bug — not fixed, flagged separately), deleted 49 ad hoc `.bak-*`
  files (one had plaintext secrets) and gitignored the pattern, pushed the branch.
- **PR needs manual open+merge** (no `gh` CLI in this environment):
  https://github.com/winfer70/ProjectNemo/pull/new/feature/heimdall-config-sync-20260820
- **URGENT — rotate 3 secrets**: `heimdall_memory_token`, `influxdb_token`, and the Satel
  `alarm_code` were briefly printed in plaintext to a terminal during config validation
  (`check_config --secrets`, a mistake — won't repeat). Rotate all three.

## What Was Accomplished

### Heimdall — Task 7 (M6: automated test matrix + soak-test logging) shipped

This closes out the **entire original 8-task Heimdall brief** (Task 0 through
Task 7 = M0–M6), plus one add-on (Task 8, persistent memory) requested
mid-project. All 8 original tasks + the add-on are now built, live-verified,
and merged to `dev` except Task 7 itself, which is pushed and awaiting PR
merge (see Next Actions).

- Built `heimdall/tests/test_matrix.py` — a live regression suite exercising
  every entity-domain row from the brief across EN/PL × Gemini/qwen via HA's
  `conversation.process` REST API (gate exposure-check, light switch,
  climate/TRV, aquarium read+write, calendar read+write, open-domain,
  ambiguous mixed-language). Documented, deliberate deviations from the
  literal brief where the assumptions didn't match live infra (only one
  Google Calendar account exists; no `calendar.delete_event` service exists,
  so calendar writes are opt-in; gate is exposure-check-only, no physical
  actuation, per an explicit safety call).
- Built `heimdall/scripts/ntfy_failure_logger.py` — a poll-based (not
  streaming) subscriber for a dedicated `heimdall-failures` ntfy topic,
  appending failures to `heimdall/SOAK_LOG.md`. Provisioned a fresh
  `heimdall_bot` ntfy user/token on `nemo-ntfy` (vesemir) from scratch — no
  ntfy users/tokens existed before this task.
- **Running the matrix for the first time found two real, previously
  unknown bugs**: a phantom Tuya `light.office_light`/`fan.office_light`
  pair (powered downstream of the real office relay, so reports
  `unavailable` whenever the relay is off) had a cleaner name than the real
  relay and was winning Assist's fuzzy voice-matching for both agents and
  both languages, silently "succeeding" against an unreachable entity. Fixed
  by hiding both from Assist exposure.
- Diagnosed (but, per the user's explicit call, did not chase further) two
  qwen-only entity-resolution gaps: qwen resolves "office light" to a real,
  separate device (`switch.office_led`) instead of the intended relay; qwen
  also cannot resolve the bedroom radiator via an added entity-registry
  alias (tried two aliases, then reverted to one — aliases appear to only
  feed HA's built-in intent matcher, not qwen's own tool schema). Both are
  reported as a distinct `KNOWN-LIM` status in the test matrix output —
  visible, not silently hidden, not counted as suite failures.
- Also documented a Google Gemini free-tier rate-limit finding (~15
  requests/minute ceiling, a full run makes ~13 calls) as a known constraint
  on back-to-back full runs, not a code bug.
- Full writeup: `heimdall/TEST_MATRIX.md` (new) and `heimdall/HA_CONFIG_CHANGES.md` section 9.
- Guardrail clean (41 files, no alarm-related exposure). Full pytest suite
  132/132 passed. **Final live test-matrix run: 25/25 implementable checks
  passed** (1 N/A, 2 skipped-by-default, 4 known-limitation).

### Prior sessions (already merged to `dev`, unaffected this session)
- Task 0 — alarm-exposure CI guardrail
- Task 1 (M0) — GPU/STT benchmark
- Task 2 (M1) — Wyoming STT/TTS + Assist pipelines
- Task 3 (M2) — local qwen2.5:7b-instruct tool-calling agent + entity exposure
- Task 4 (M3) — aquarium tools
- Task 5 (M4) — Google Calendar integration
- Task 6 (M5) — n8n AI task router
- Task 8 (M7, add-on) — persistent cross-session conversation memory

(Public-repo security remediation from the 2026-08-15 handoff is complete
and superseded by this entry — WiFi password rotation follow-up from that
session should be confirmed done separately if not already.)

## Current State
- Branch `feature/heimdall-task7-test-matrix` is pushed (2 commits: feature
  + graphify chore) but **its PR has not yet been opened/merged**.
- Every other Heimdall task (0–6, 8) is merged to `dev`.
- One stray real-world artifact remains: a test calendar event ("Gemini
  regression check", 2026-08-20) on the live Google Calendar with no
  automated way to delete it (no `calendar.delete_event` service in this HA
  version).

## Exact Next Actions

1. **Open and merge the Task 7 PR**: https://github.com/winfer70/HomeAI/compare/dev...feature/heimdall-task7-test-matrix?expand=1
   (no `gh` CLI available in this environment, so this needs a manual click-through).
2. **Manually delete the stray "Gemini regression check" calendar event**
   via Google Calendar's own UI.
3. Once merged, the entire Heimdall brief (all 8 original tasks + the
   memory add-on) is fully shipped. Any further work is new scope beyond
   what was originally planned — confirm with the user before starting
   anything not already discussed.

## Blockers
- None blocking further Heimdall work — only the PR-merge step above is
  outstanding, which requires manual GitHub action (no `gh` CLI here).
- Carried over from the 2026-08-15 session (verify still resolved): the
  previously exposed WiFi password should have been rotated after the
  public-repo sanitization pass — re-confirm this happened if not already
  independently verified.
