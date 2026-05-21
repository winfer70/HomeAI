# Husaria Beats — Automation Reference

## Albums & Release Schedule

| Album | Target | Songs | Status |
|---|---|---|---|
| Standalone (8 songs) | Live | Husaria, Wyklęci, Syberia, Enigma, Czerwone Maki, Dywizjon 303, Cud nad Wisłą, Cichociemni | ✅ Released |
| **KREW I CHWAŁA** | Apr 2026 | 10 + Intro (major battles 1241–1683) | ✅ Released |
| **Trzeci Maja 1791** | 3 May 2026 | Standalone (national holiday) | ✅ Ready to publish |
| **ZAPOMNIANI** | Jun 2026 | 10 + Intro (WWII forgotten heroes) | ✅ All videos ready |
| **GRANICE** | Jul 2026 | 9 songs (partitions & uprisings) | 3 songs ready, 6 pending |
| Powstanie Warszawskie | 1 Aug 2026 | Standalone anniversary | Ready |
| **SOLIDARNI** | Sep 2026 | 9 songs (WWII resistance + Solidarity) | 2 ready, Katyń on hold |
| **PIERWSZE DNI** | 1 Sep 2026 (fixed) | 7 songs (Sep 1939) | Placeholder |
| **SZPIEDZY I GENIUSZE** | Q4 2026 | 9 songs (codebreakers/spies) | Placeholder |
| **DYWIZJON 303** | Nov 2026–Mar 2027 | 7 songs (303 Squadron) | Placeholder |
| **KOBIETY ŻELAZA** | Mar 2027 | 11 songs (women of Polish history) | Placeholder |
| **PODZIEMNA POLSKA** | Q2 2027 | 10 songs (underground culture) | Placeholder |
| **MORZE I NIEBO** | Q3 2027 | 9 songs (naval/air) | Placeholder |

---

## ZAPOMNIANI Songs — Full Detail

| Song | PL Title | EN Title | Subject |
|---|---|---|---|
| Captain_Pilecki | Rotmistrz Pilecki | Captain Pilecki | Voluntarily infiltrated Auschwitz, smuggled Holocaust reports to Allies who ignored him, executed by communists 1948 |
| Wojtek_the_Bear | Miś Wojtek | Wojtek the Soldier Bear | Bear mascot of Polish 2nd Corps, carried shells at Monte Cassino, ended up in Edinburgh Zoo |
| General_Maczek | Maczek — Wymazany | The General They Erased | 1st Polish Armoured Div — never lost a battle, liberated Breda, stripped of citizenship/pension by communists, worked as Edinburgh barman |
| Kosacki_Mine_Detector | Zapomniany Wynalazca | The Forgotten Inventor | Invented world's first portable mine detector in Scotland 1941, gave patent to British for free, used at El Alamein, died anonymous |
| ŁączniczkiAK | Łączniczki: Niewidzialna Armia | Invisible Army | Female AK couriers — backbone of Polish resistance, smuggled orders/weapons through occupied Warsaw, erased by communists postwar |
| Jerzy_Sosnowski | Cień Berlina | Shadow of Berlin | Master spy in 1920s-30s Berlin, uncovered Nazi rearmament plan, imprisoned by Germans, killed by Soviets |
| Sosnkowski_Kazimierz | Sosnkowski: Wódz, Którego Uciszyli | The Commander They Silenced | Supreme Commander warned Allies about Yalta, condemned Western silence over Warsaw Uprising, sacked by Churchill, died in Canadian exile |
| Fieldorf_Nil | Nil: Żelazny Wyrok | Nil: The Iron Sentence | Commanded Kedyw (killed Kutschera/Butcher of Warsaw), survived Nazis + Soviet gulags, hanged by communist Poland 1953, body never found |
| Groszkowski_Janusz | Ojciec Fali Podziemia | The Father of the Underground Wave | Wired AK radio network, decoded V-2 rocket, died 1984 with patents stolen and name erased |
| Sosabowski_Stanislaw | Sosabowski — Wódz Orłów | Sosabowski — Leader of Eagles | Warned Allies Market Garden would fail at Arnhem, was right, scapegoated by British, warehouse laborer for 17 years, Order of William awarded posthumously |
| Intro | ZAPOMNIANI — Intro | The Forgotten — Intro | Album intro — sets up the Double Betrayal arc across all 10 songs |

---

## Song Production Flow (7 Phases)

Every song goes through these phases in order:

```
Phase 1 — LYRICS
  PL/lyrics_clean.txt      ← subtitle source, literary Polish, no tags
  PL/lyrics_suno.txt       ← Suno generation copy (EN section tags + voice tags)
  PL/suno_style_pl.txt     ← Suno style prompt
  EN/lyrics_clean_en.txt   ← subtitle source, literary English
  EN/lyrics_suno_en.txt    ← Suno generation copy
  EN/suno_style_en.txt     ← Suno style prompt

Phase 2 — AUDIO
  Suno → generates audio from lyrics_suno.txt
  PL: audio_pl.mp3 → Remotion/public/{key}/audio_pl.mp3
  EN: audio_en.mp3 → Remotion/public/{key}/audio_en.mp3

Phase 3 — VOCAL ISOLATION
  python scripts/vocal_isolate_{key}.py   ← Demucs htdemucs
  Output: Remotion/public/{key}/vocals_pl.wav
          Remotion/public/{key}/vocals_en.wav

Phase 4 — LYRIC SYNC
  python scripts/sync_all.py --song {key} --method stable
  Output: Remotion/src/songs/{SongTitle}/data/lyrics_pl.ts
          Remotion/src/songs/{SongTitle}/data/lyrics_en.ts
  QA: 3-pass auto-retry, chorus cramming fix, gap checks

Phase 5 — IMAGES
  Leonardo AI (Essential tier) → JPG scene images
  Format: s{N}_{scene_id}.jpg → Remotion/public/{key}/scenes/
  15-20 images per song (1920×1080, cinematic oil painting style)

Phase 6 — VIDEO RENDER
  Remotion compositions: {SongTitle}PL + {SongTitle}EN
  + PromoShort PL/EN (1080×1920 vertical)
  + Feed PL/EN (1080×1350)
  Command: npx remotion render {Id} {out}.mp4 --codec h264 --crf 18

Phase 7 — DESCRIPTIONS + META
  PL/description_youtube.txt   ← 250-350 words, Rule 4 format
  PL/tags_youtube.txt          ← under 500 chars, starts "Husaria Beats"
  EN/description_youtube.txt   ← 250-350 words, Rule 5 format
  EN/tags_youtube.txt
  PL/fb_ig_pl.txt              ← 80-130 words
  PL/tiktok_pl.txt             ← 3 facts, under 150 words
  EN/fb_ig_en.txt
  EN/tiktok_en.txt
  meta.json                    ← n8n automation source (song root)
```

---

## Per-Song Folder Structure

```
SongName/
├── meta.json                    ← n8n upload metadata
├── PL/
│   ├── lyrics_clean.txt         ← literary Polish, no Suno tags, subtitle source
│   ├── lyrics_suno.txt          ← EN section tags + inline voice/delivery tags
│   ├── suno_style_pl.txt        ← Suno style prompt string
│   ├── description_youtube.txt  ← Polish YouTube description (250-350 words)
│   ├── tags_youtube.txt         ← Polish YouTube tags (under 500 chars)
│   ├── fb_ig_pl.txt             ← Polish Facebook + Instagram post
│   └── tiktok_pl.txt            ← Polish TikTok caption
└── EN/
    ├── lyrics_clean_en.txt      ← literary English, subtitle source
    ├── lyrics_suno_en.txt       ← EN section tags + inline voice/delivery tags
    ├── suno_style_en.txt        ← Suno style prompt string
    ├── description_youtube.txt  ← English YouTube description (250-350 words)
    ├── tags_youtube.txt         ← English YouTube tags (under 500 chars)
    ├── fb_ig_en.txt             ← English Facebook + Instagram post
    └── tiktok_en.txt            ← English TikTok caption
```

---

## meta.json Schema (n8n interface)

```json
{
  "title_pl": "{PL title} | HusariaBeats",
  "title_en": "{EN title} | HusariaBeats",
  "album_name_pl": "ZAPOMNIANI",
  "album_name_en": "The Forgotten",
  "description_pl": "...\n\n...",
  "description_en": "...\n\n...",
  "tags_pl": ["husariabeats", "..."],
  "tags_en": ["husariabeats", "..."]
}
```

**Rules:**
- `title_en`, `description_en`, `tags_en` — omitted entirely for PL-only songs
- n8n checks `if (meta.description_en)` to decide whether to upload EN version
- Tags: arrays, no `#` prefix, always starts with `"husariabeats"`
- `album_name_pl` / `album_name_en` — set per album (e.g. ZAPOMNIANI / The Forgotten)

---

## Release Checklist (per song, pre-upload)

```
□ Pronunciation QA passed (scripts/pronunciation_qa.py — Groq Whisper)
□ lyrics_clean.txt finalized (PL + EN)
□ Audio mp3 confirmed (audio_pl.mp3 + audio_en.mp3 in Remotion/public/)
□ Lyric sync QA passed (no gaps >300fr, no zero-duration lines, line count matches)
□ Scene images all present (s{N}_{scene_id}.jpg in Remotion/public/{key}/scenes/)
□ Video rendered (main PL + EN, Feed PL + EN, Short PL + EN)
□ meta.json written and validated (JSON parses, all required fields present)
□ DistroKid upload done (~1 day lead before YouTube publish date)
□ YouTube PL uploaded and scheduled
□ YouTube EN uploaded and scheduled
□ Social posts scheduled (IG/FB/TikTok PL + EN)
```

---

## Key Automation Touch Points

| Step | Tool | Notes |
|---|---|---|
| Audio generation | Suno Pro | Manual — paste `lyrics_suno.txt` into Suno UI |
| Vocal isolation | Demucs (Python script) | `python scripts/vocal_isolate_{key}.py` |
| Lyric sync | stable-ts (Python script) | `python scripts/sync_all.py --song {key} --method stable` |
| Image generation | Leonardo AI Essential | Manual in Leonardo UI; ~15-20 images per song |
| Video render | Remotion | `npx remotion render` — 4 compositions per song (main PL/EN + Feed PL/EN + Short PL/EN) |
| DistroKid upload | Manual | No API — batch CSV only; human must submit; ~1 day lead required |
| YouTube upload | n8n + YouTube Data API v3 | Reads `meta.json`; OAuth credentials not yet set up (needs Google Cloud Project) |
| Social posting | n8n | Auto-post (not draft); min gap configurable in DB `settings` table |
| DB status updates | n8n webhook | Song status: draft → scheduled → released |
| Admin panel | Internal (Cloudflare Access) | Not public; sets release dates + triggers pipeline steps |
| Voting close | n8n trigger | Auto-close when song assigned release date → adds "Planned Release" badge |

---

## Important Constraints for Automation Design

- **YouTube Data API v3 OAuth** — not yet created; requires one-time Google Cloud Project setup
- **DistroKid** — no API exists; script can prepare batch CSV but human must do final submit
- **Social post rate limiting** — default 1 song/day gap; stored in DB `settings` table so it's changeable without code deploy; critical for album releases (10 songs over 10 days)
- **n8n instance** — already running at `kamilon8n.win` (Docker); integrate here before building new tooling
- **PostgreSQL DB** — single source of truth for song/album release status; scripts and n8n read/write it
- **Bilingual uploads** — every song has PL + EN version; n8n uses `if (meta.description_en)` to conditionally upload EN; PL-only songs have no EN fields in `meta.json`
- **DistroKid lead time** — Spotify needs ~1 day before YouTube publish date; plan scheduling accordingly
- **Social posting** — AUTO-POST, not draft; rate limit is configurable; album drops require bursting (e.g. 10 posts in 10 days)

---

## Suno Style Prompt Guide

```
[Genre/style], [Vocal spec], [Delivery mood], [Instrumentation], [BPM], [Polska wymowa — PL only]
```

| Song type | BPM range |
|---|---|
| Battle / aggressive | 130–145 |
| Hero / courageous | 88–100 |
| Tragedy / resistance | 80–90 |
| Emotional / bittersweet | 75–88 |

PL prompt always ends with `Polska wymowa`. EN prompt does not.

---

## Double Betrayal Arc (mandatory in every song)

Every song must contain BOTH halves:
1. **West's Silence** — Yalta, visas denied, erased from Western history books, Allies ignored Polish warnings
2. **Communist Erasure** — show trials, name scrubbed from Polish textbooks, family persecuted, rehabilitation only after 1989

Arc formula: *hero defeats Nazis → betrayed by West (Yalta/silence) → erased by communists → Husaria Beats restores the memory*

Never deliver one half without the other.
