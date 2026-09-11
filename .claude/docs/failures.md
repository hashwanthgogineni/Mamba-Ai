# Failure catalogue

Every bug that reached a user, its real cause, and why the gates missed it.
Ordered by what they taught us.

---

## 1. The pipeline failed open — the cause behind all the others

```python
export = await self._export_web(project)   # ran unconditionally
"success": export["success"]               # = "did files appear on disk"
```

Every gate ran, found problems, logged them — and was **ignored at the decision
point**. "Success" meant the export wrote files, not that the game worked.

Six of eleven generated games shipped broken.

**Fixed:** blocking issues refuse to export. `BLOCKING_MARKERS` in
`godot_validator.py` defines which failures mean "this is not a game".

---

## 2. Player with no script

A platformer shipped with `[node name="Player" type="CharacterBody2D"]` and no
`script =` line. `player.gd` had never been generated — token exhaustion killed
it, the builder logged "Script generation failed" and carried on.

A `CharacterBody2D` with no script is an inert box: no movement, no input, no
errors. Every gate passed because nothing *threw*.

Worse: the runtime harness already tracked `player_moved` and **printed it
instead of failing on it**. The instrument existed and was not wired up.

**Fixed:** three gates — a promised file that does not exist fails the build;
`NO_SCRIPT` on any scriptless physics body; `PLAYER_INERT` when the player never
moves in 300 frames.

---

## 3. The AI graded its own homework

A shooter shipped with an empty `Enemies` container and no spawner. It passed
because the plan declared the manifest to verify as
`['Player', 'Player/Shape', 'HUD', 'HUD/ScoreLabel']` — enemies were never on
the list.

**The check was self-graded, so it passed by promising nothing.**

**Fixed:** `expected_content()` derives the minimum from the plan's *level data*
(enemies, collectibles, platforms, grid contents) and the runtime counts what
actually exists. Declaring 8 enemies and shipping 0 is now `TOO_FEW_ENEMY`.

---

## 4. …and then over-declared

The inverse of #3. The planner declared `Coin.tscn` would contain a node named
`Body`; the file-writer built a perfectly good coin whose root was `Coin`. The
gate believed the plan and failed a working scene.

**Fixed:** node names are only asserted for the **main** scene, where the level
script genuinely looks containers up by name. What matters about an entity scene
— that it draws and has a script — is covered by `NO_VISUAL` / `NO_SCRIPT`.

---

## 5. Invisible enemies

`Ghost.tscn` had a script and a `CollisionShape2D` and **no visual node at all**.
Structurally perfect, completely invisible. Every gate passed.

**Fixed:** `NO_VISUAL` — an entity scene whose root is a physics body must have
a drawable descendant. Only the root is checked, because child `Area2D` triggers
legitimately have no visual and a false positive is worse than no gate.

---

## 6. 187 issues in one scene

After the level examples were enriched 10×, `Main.tscn` had to contain ~30 entity
nodes, each needing a correct resource id and a hand-counted `load_steps`.

This is arithmetic, and arithmetic is not what a language model is for.

**Fixed:** levels are built in code. `Main.tscn` holds containers, the player and
the HUD (~6 nodes); the level script spawns everything in `_ready()` from
constants. Result: **187 issues → 0**, and the full static suite passed for the
first time.

---

## 7. Thin, empty-looking games

Not a bug in the model. The prompt said:

> *"Keep it to 2-4 scripts and 1-3 scenes. A small game that works beats a large
> one that does not."*

…and showed an example with 2 platforms, 1 enemy, 2 collectibles. Every game
came out with 3-5 enemies and 4-8 platforms. **The model obeyed precisely.**

**Fixed:** instruction reversed, examples enriched 10× (platformer: 10 platforms
/ 6 enemies / 16 collectibles; maze: a real 28×22 grid with 256 pellets), plus a
density rule stating the example is the *minimum*.

---

## 8. Token exhaustion, twice

Thinking mode spends part of the budget reasoning before answering. 32 K was not
enough. Then enriching the examples (#7) made the *plan* bigger and broke it
again in the same way.

**Fixed:** 64 K everywhere, plus a fallback that retries the plan without
thinking rather than failing the whole build.

---

## 9. Every prompt rebuilt from scratch

"Tell me what to change and I will build it again" — and it did, literally.
A follow-up threw away a game that had passed every gate and generated a new one.

**Fixed:** the plan is persisted to `mamba_plan.json`; follow-ups load it plus the
current file contents, the AI picks which 1-2 files to change, and only those are
rewritten. Same project id, same preview.

---

## 10. Duplicate WebSocket messages

React `StrictMode` double-invokes effects in dev. The socket is created
asynchronously, so cleanup ran before the promise resolved and left a second live
socket — every message arrived twice.

**Fixed:** a `cancelled` flag closes any socket that arrives after teardown.

---

## The pattern

Every one of these is **mechanical work given to a model**, or **a gate that
believed a declaration instead of reality**, or **a pipeline that logged a
failure and continued**.

None is the model being bad at game design.
