# Mamba — AI game generation

Turns one sentence into a playable Godot 4 game, validated inside the engine
before it is ever shown to a user.

Repo is still named `Gamora-Ai` on disk; the product is **Mamba**. Only
user-visible strings were renamed — component names, CSS variables and the
directory kept the old name deliberately.

---

## The one principle that matters

> **AI writes intent. Code writes structure.**

Almost every failure this project has had came from asking the model to do
*mechanical* work — counting `load_steps`, assigning resource ids, keeping a
declaration consistent with an implementation. None came from it being bad at
game design.

The evidence is unambiguous:

| Written by | Failure rate across 11 games |
|---|---|
| `project.godot`, `export_presets.cfg` (templated by code) | **0** |
| Levels built in a `for` loop from plan data | **0** |
| Hand-written `.tscn` with ~30 entity nodes | 187 issues in one file |

When in doubt, move work from the model to the emitter.

---

## Pipeline

```
prompt
  → clarify        classify genre; ask 0-3 questions ONLY if genuinely unsure.
                   Pauses here — no project, no build, no spend, until answered.
  → plan           genre-specific JSON: mechanics + level data + file list
  → sprites        Kenney CC0 art fetched into the project (cached on disk)
  → scripts        each generated, linted, compiled, repaired in place until green
  → scenes         same loop, once the scripts they reference exist
  → gates          whole-project static validation
  → --import       MANDATORY, or assets never enter the .pck
  → runtime        boots the real scene headless for 300 frames
  → FAIL CLOSED    blocking issues refuse to export
  → export         Godot web build (~38 MB)
  → serve          /api/v1/generate/play/{id}/{file}
```

Roughly **20 AI calls** and **2–10 minutes** per game. That cost is the main
open problem — see `docs/roadmap.md`.

---

## Layout

```
core/
  services/
    game_genres.py         6 genres, each with its own level/mechanics schema
    ai_game_clarifier.py   classify + decide whether to ask anything
    ai_godot_generator.py  plan → files → repair → edit  (all AI calls)
    godot_emitter.py       project.godot, export_presets.cfg, icon  (templated)
    asset_library.py       Kenney CC0 sprites, verified paths, disk cache
    gdscript_lint.py       instant Python checks, no subprocess
    godot_validator.py     static gates (stderr + in-engine assertions)
    godot_runtime.py       runtime smoke test + content assertions
    godot_builder.py       orchestrates everything, owns the repair loop
    local_store.py         in-memory DB + disk storage for LOCAL_MODE
  scripts/
    check_gates.py         regression suite over generated projects (NO AI, free)
    check_deepseek.py      verify the API key and model actually work
src/
  components/
    GamoraAIMain.tsx       prompt entry, clarify questions
    GamoraAIDashboard.tsx  chat + live preview; follow-ups EDIT the game
    ClarifyQuestions.tsx   option cards shown while the build is paused
    GenerationLoader.tsx   progress ring
```

---

## Running it

```bash
cd core && python3 main.py     # :8000
npm run dev                    # :8080
```

`core/.env` (gitignored) needs only `DEEPSEEK_API_KEY` while `LOCAL_MODE=true`.

**Restart the backend after any Python change.** There is no auto-reload unless
`DEBUG=true`, and testing against a stale process has wasted real time here.

### Modes

| Flag | Effect |
|---|---|
| `LOCAL_MODE=true` | No Supabase, no database, no auth. State in memory, games on disk. |
| `AUTH_ENABLED=false` | Every request runs as a fixed dev user. Defaults to `true` so forgetting it can never open a deployment. |
| `GAME_ENGINE=godot` | The Godot pipeline. `html5` falls back to the original single-file path. |
| `DEEPSEEK_THINKING` | `true` = best quality, slowest, most expensive. |

---

## Before changing a gate

```bash
python core/scripts/check_gates.py --expect
```

Runs every gate over the generated projects on disk. **Zero AI calls** — Godot
is local and free. Three real bugs are pinned as fixtures; if a gate stops
catching one, this fails.

Add a fixture whenever a new class of bug is found.

---

## Read these before making changes

- `docs/godot-facts.md` — measured engine behaviour. Exit codes lie. Read it
  before writing any validation.
- `docs/failures.md` — every bug, its root cause, and why the gates missed it.
- `docs/roadmap.md` — what is next and why.
