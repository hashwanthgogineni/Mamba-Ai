# Godot 4.7 — measured behaviour

Everything here was verified by deliberately breaking a project and observing
what Godot actually does. None of it is from documentation, and several points
contradict what you would reasonably assume.

Godot at `/opt/homebrew/bin/godot` (4.7.2). Export templates at
`~/Library/Application Support/Godot/export_templates/4.7.2.stable` (1.9 GB).

---

## Exit codes are useless

```bash
godot --headless --check-only --script res://broken.gd
echo $?    # 0 — even with a parse error
```

**Never branch on the exit code. Scan stderr.**

---

## What each failure actually produces

| Break | Detected by | Signal |
|---|---|---|
| GDScript syntax error | stderr | `SCRIPT ERROR: Parse Error: ...` |
| Spaces instead of tabs | stderr | `Used tab character ... instead of space` + line |
| Missing `ext_resource` path | stderr | `res://X.tscn:25 - [ext_resource] referenced non-existent resource` |
| Bad `parent=` path | **in-engine assert only** | warns, then creates a node literally named `Parent#Child` at the root |
| Wrong `load_steps` count | **nothing** | silently tolerated |
| Trailing garbage in `.tscn` | **nothing** | silently ignored |
| Body with no script | **in-engine assert only** | loads fine, throws nothing, does nothing |
| Entity scene with no visual | **in-engine assert only** | loads fine, invisible in game |

Godot is far more permissive than expected. `load()` returning `null` is **not**
a reliable gate.

---

## Therefore: three layers, none of them the exit code

1. **stderr scan** — parse errors, missing resources.
   Filter exit-time noise (`leaked`, `still in use`, `RID alloc`); it appears on
   healthy runs and will otherwise cry wolf.
2. **in-engine assertions** — a `SceneTree` script that loads and instantiates
   every scene, then asserts: no node name contains `#`, every physics body has
   a script, every entity scene root draws something.
3. **runtime smoke test** — boot the real main scene for 300 frames. Assert the
   player exists, is not inert, and that the level contains what the plan
   promised.

---

## False positives are worse than no gate

Three separate times a bad gate made the repair loop **rewrite working code into
worse code**. A gate you cannot trust is a liability, not a safety net.

**Autoloads are not registered in headless script runs.** A correct
`GameManager.add_score()` reports as `Identifier not found: GameManager` under
both `--check-only` and `--script`. Two fixes, both applied:
- the runtime harness installs singletons by hand, mirroring the engine
- any `Identifier not found: <autoload name>` is filtered out regardless

**`get_tree().current_scene` is null in a `SceneTree` script** unless the
harness sets it. Any game calling `reload_current_scene()` otherwise reports a
failure that is the harness's fault, not the game's.

**Node names invented by the planner are not a contract.** The planner declares
node paths before the file exists; the file-writer reasonably picks different
names. Asserting them fails good scenes. Only the main scene's container names
are asserted, because the level script looks *those* up by name.

---

## Export

```bash
godot --headless --path <abs> --export-release "Web" <abs>/dist/index.html
```

- **Paths must be absolute.** Godot resolves the export target relative to
  `--path`, so a relative target silently writes nowhere and reports nothing.
- **The target directory must already exist.**
- **The preset name must match `export_presets.cfg` exactly.**
- **`--import` must run first** or assets never enter the `.pck`. The game runs;
  the textures are missing.
- **`thread_support=false`.** Single-threaded is the Godot 4 default and needs
  no `Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy` headers, so
  the preview can be served from any static path.

Output is `index.html` + `.wasm` + `.pck` + `.js` + `.png`, about **38 MB** —
almost all of it the engine. A tiny game's `.pck` is ~15 KB. Serve gzipped;
the `.wasm` compresses about 4×.

`.wasm` **must** be served as `application/wasm` or streaming compilation fails.
