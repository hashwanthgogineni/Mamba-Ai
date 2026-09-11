# Roadmap

---

## Next: the AI stops writing `.tscn` entirely

The single highest-leverage change left, and it follows directly from the
evidence in `failures.md`.

Today the model writes ~10 files, four of them scenes. Scenes are where almost
every structural failure has happened. But entity scenes are **completely
formulaic**:

```
Player.tscn = CharacterBody2D + CollisionShape2D + Sprite2D + script
Enemy.tscn  = same shape
Coin.tscn   = Area2D        + CollisionShape2D + Sprite2D + script
Main.tscn   = root + containers + player + HUD
```

There is no creative decision in any of that. `godot_emitter.py` should generate
all of it from the plan, exactly the way it already generates `project.godot` and
`export_presets.cfg` — both of which have **never failed once across 11 games**.

**The model would then write only `.gd` files: pure logic, no arithmetic.**

Five bug classes stop being possible rather than being caught faster:

| Failure | After |
|---|---|
| wrong `load_steps` | impossible — code counts |
| bad resource ids | impossible — code assigns |
| `MISSING_NODE` | impossible — code builds what the plan declares |
| `NO_VISUAL` | impossible — the template always includes a sprite |
| `NO_SCRIPT` | impossible — the template always attaches one |

**Cost:** less flexibility for genuinely unusual scenes. Mitigation — templates
cover the formulaic 90%, and anything unusual is done at runtime in GDScript,
which is where creativity belongs anyway.

**Where to start:** `godot_emitter.py`. It already owns the templated files;
give it `emit_entity_scene()` and `emit_main_scene()` driven by the plan, then
drop scenes from `generate_files()`.

---

## Speed — about 20 AI calls per game, 2-10 minutes

Measured on a real run: 10 first drafts + 9 repairs + plan + clarify, every one
with thinking at high effort and a 64 K budget.

Cheapest wins, roughly in order:

1. **Thinking off for repairs.** A repair is mechanical — it is handed the exact
   error and the exact file. This alone should roughly halve wall-clock.
2. **Templated scenes** (above) remove ~4 generations *and* their repair rounds.
3. `DEEPSEEK_REASONING_EFFORT=low` — one line in `core/.env`, no code change.
4. Gzip the `/play` route: 38 MB → ~10 MB on first load.

The cost ladder is worth keeping in mind when adding any check:

```
Python lint    ~0 ms    free
Godot check    ~1.5 s   free
AI repair      ~30 s    costs money
```

Push every check as far down that ladder as it will go.

---

## Known open bugs

- **Collision is not verified.** A generated Pac-Man had zero collision handlers
  in all four scripts — the player walks through walls. The runtime test only
  checks the player does not leave the world. A gate should assert that a
  collision actually fires during the smoke test.
- **Only 2 of 20 enemies spawn** in the latest platformer. `_spawn_enemies()`
  reads correctly on inspection, so something fails silently at runtime.
- **Iteration is untested end to end.** The code path exists and compiles; no
  follow-up edit has been run through it.

---

## Dead code the first audit flagged, still present

Harmless at runtime but actively misleading:

- `agents/asset_manager.py` — 1,222 lines, instantiated at startup, never called.
  Confusing now that `asset_library.py` is the real one.
- `services/genre_registry.py` — 597 lines, unreachable.
- `core/orchestrator.py` — ~1,200 lines of disconnected pipeline stages.
- `services/web_game_service.py` — the HTML5 path, still initialised under
  `GAME_ENGINE=godot`.
- Two `DeepSeekClient` instances are created at startup, so a config change has
  to land in two places.

---

## Deferred by choice

- **3D.** Low-poly CC0 (Kenney, Quaternius) is viable in a browser; photoreal is
  not — 38 MB is the *empty* engine. The asset plumbing is identical for `.glb`,
  so this is much cheaper after 2D is proven.
- **Supabase / auth.** Disabled behind flags, not removed. Both default to the
  safe setting.
- **Audio.** Kenney's CC0 library has 295 audio files; nothing uses them yet.
