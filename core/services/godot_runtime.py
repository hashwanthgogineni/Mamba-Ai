"""
Runtime smoke test.

Every other gate is static: the project parses, loads and instantiates. None of
them run the game. A game can pass all of them and still throw on frame 1, or
drop the player through the floor, or never move at all.

This boots the real main scene headless, steps it for a few hundred frames, and
reports anything that goes wrong — with the file and line Godot itself gives us,
so the repair stage can target the right file.

Isolated per-script execution is deliberately NOT done here: a script pulled out
of its scene fails on `$Child` lookups that are perfectly correct in context,
and a false positive is worse than no check because the repair loop believes it.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from services.godot_validator import Issue, ValidationResult

logger = logging.getLogger(__name__)

_RUNTIME_ERROR = re.compile(
    r"(?:SCRIPT ERROR|ERROR):\s*(?P<msg>.+)", re.I
)
_AT_LOCATION = re.compile(r"at:\s*.*?\((?P<file>res://[^\s:)]+):(?P<line>\d+)\)")
_RES_PATH = re.compile(r"res://(?P<file>[A-Za-z0-9_\-/.]+\.gd)")

_NOISE = (
    "were leaked", "still in use", "RID allocation",
    "RIDs of type", "ObjectDB instances", "--- Debugging process stopped",
)


# Role keywords used to recognise a node by name. The planner names things
# conventionally (Enemy1, Coin3, Platform2), so this is good enough to tell an
# empty level from a populated one.
_ROLE_WORDS = {
    "enemy": ("enemy", "enemies", "ghost", "drone", "alien", "monster", "obstacle"),
    "collectible": ("coin", "collectible", "pellet", "orb", "gem", "star", "cell", "pickup"),
    "platform": ("platform", "ground", "floor", "wall", "tile", "brick"),
}


def expected_content(plan: dict) -> dict:
    """
    Minimum number of things the finished game must actually contain, taken
    from the plan's own level data.

    This exists because the manifest assert is self-graded: the AI declares
    which nodes to verify, so a lazy declaration passes while the level is
    empty. The plan's level data is a promise we can hold it to instead.
    """
    level = (plan or {}).get("level") or {}
    out: dict = {}

    def count(value) -> int:
        return len(value) if isinstance(value, list) else 0

    enemies = count(level.get("enemies")) or count(level.get("enemy_starts"))
    for wave in level.get("waves") or []:
        if isinstance(wave, dict):
            enemies += int(wave.get("count") or 0)

    collectibles = count(level.get("collectibles")) or count(level.get("pickups"))
    platforms = count(level.get("platforms")) or count(level.get("walls"))

    # Grid-based levels (maze) carry their content in the grid rows.
    grid = level.get("grid")
    if isinstance(grid, list) and grid and isinstance(grid[0], str):
        joined = "".join(grid)
        collectibles = collectibles or joined.count(".") + joined.count("o")
        enemies = enemies or joined.count("G")
        platforms = platforms or joined.count("#")

    if enemies:
        out["enemy"] = min(enemies, 50)
    if collectibles:
        out["collectible"] = min(collectibles, 50)
    if platforms:
        out["platform"] = min(platforms, 50)
    return out


class GodotRuntime:
    def __init__(self, godot_path: str = "godot", timeout: int = 120):
        self.godot = godot_path
        self.timeout = timeout

    async def smoke_test(
        self,
        project: Path,
        main_scene: str,
        frames: int = 300,
        autoloads: Optional[Dict[str, str]] = None,
        expect: Optional[Dict[str, int]] = None,
    ) -> ValidationResult:
        """
        Run the main scene for `frames` physics steps and collect failures.

        Autoloads are registered by hand: a `--script` SceneTree run does NOT
        install project singletons, so correct `GameManager.add_score()` reads
        as "Identifier not found" unless we put them in the tree ourselves.
        """
        singletons = {
            name: (path if path.startswith("res://") else f"res://{path}")
            for name, path in (autoloads or {}).items()
        }
        harness = (
            _RUNTIME_GD
            .replace("__MAIN_SCENE__", json.dumps(f"res://{main_scene}"))
            .replace("__FRAMES__", str(frames))
            .replace("__AUTOLOADS__", json.dumps(singletons))
            .replace("__EXPECT__", json.dumps(expect or {}))
            .replace("__ROLE_WORDS__", json.dumps(_ROLE_WORDS))
        )
        (project / "runtime_check.gd").write_text(harness, encoding="utf-8")

        cmd = [
            self.godot, "--headless", "--path", str(project.resolve()),
            "--script", "res://runtime_check.gd",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            text = out.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            return ValidationResult(
                ok=False,
                issues=[Issue(
                    file=main_scene,
                    message=(
                        f"The game hung: it did not finish {frames} frames in "
                        f"{self.timeout}s. Look for an infinite loop in _ready() "
                        f"or _process()."
                    ),
                    kind="runtime",
                )],
                raw="TIMEOUT",
            )
        except FileNotFoundError:
            raise RuntimeError(f"Godot not found at '{self.godot}'")

        issues = self._parse(text, main_scene, list(singletons.keys()))
        return ValidationResult(ok=not issues, issues=issues, raw=text)

    def _parse(self, text: str, main_scene: str, autoloads: Optional[List[str]] = None) -> List[Issue]:
        issues: List[Issue] = []
        seen = set()
        lines = text.splitlines()

        for idx, raw in enumerate(lines):
            line = raw.strip()
            if not line or any(n in line for n in _NOISE):
                continue

            # Assertions raised by the harness itself.
            if line.startswith("RUNTIME_FAIL"):
                payload = line[len("RUNTIME_FAIL"):].strip()
                kind, _, detail = payload.partition(" ")
                key = ("runtime", detail)
                if key not in seen:
                    seen.add(key)
                    issues.append(Issue(file=main_scene, message=f"{kind}: {detail}", kind="runtime"))
                continue

            match = _RUNTIME_ERROR.search(line)
            if not match:
                continue
            message = match.group("msg").strip()
            if message.startswith("Parse Error") and "runtime_check.gd" in line:
                continue
            # Belt and braces: even with singletons installed, never let an
            # autoload name become a repair instruction.
            if any(f"Identifier not found: {a}" in message for a in (autoloads or [])):
                continue

            target, lineno = main_scene, None
            # Godot puts the location on the following "at:" line.
            for look in lines[idx: idx + 4]:
                loc = _AT_LOCATION.search(look)
                if loc:
                    target = loc.group("file").replace("res://", "")
                    lineno = int(loc.group("line"))
                    break
            else:
                named = _RES_PATH.search(line)
                if named:
                    target = named.group("file")

            if "runtime_check.gd" in target:
                continue
            key = (target, message)
            if key in seen:
                continue
            seen.add(key)
            issues.append(Issue(file=target, message=message, line=lineno, kind="runtime"))

        if issues:
            logger.warning(f"Runtime smoke test found {len(issues)} issue(s)")
            for issue in issues[:6]:
                logger.warning(f"   {issue.as_prompt_line()}")
        else:
            logger.info("✅ Runtime smoke test passed")

        return issues


# Harness executed inside Godot. Placeholders substituted before writing.
_RUNTIME_GD = '''extends SceneTree
# Generated by godot_runtime.py — do not edit by hand.
# Boots the real main scene and steps it, so runtime failures surface before
# the game reaches a player.

const MAIN_SCENE := __MAIN_SCENE__
const FRAMES := __FRAMES__
const AUTOLOADS := __AUTOLOADS__
const EXPECT := __EXPECT__
const ROLE_WORDS := __ROLE_WORDS__

var _frames := 0
var _root: Node = null
var _start_pos := Vector2.ZERO
var _player: Node = null
var _moved := false

func _init() -> void:
\t_install_autoloads()
\tvar packed = load(MAIN_SCENE)
\tif packed == null:
\t\tprint("RUNTIME_FAIL LOAD_FAILED main scene could not be loaded: ", MAIN_SCENE)
\t\tquit(1)
\t\treturn
\t_root = packed.instantiate()
\tif _root == null:
\t\tprint("RUNTIME_FAIL INSTANTIATE_FAILED main scene could not be instantiated")
\t\tquit(1)
\t\treturn
\t# Adding to the tree triggers _ready() on every node.
\tget_root().add_child(_root)
\t# The engine sets this for a normal run. Without it any game calling
\t# reload_current_scene() errors with 'Parameter "current_scene" is null',
\t# which is a fault in the harness, not in the game.
\tcurrent_scene = _root
\t_player = _find_player(_root)
\tif _player != null and _player is Node2D:
\t\t_start_pos = (_player as Node2D).global_position

func _process(_delta: float) -> bool:
\t_frames += 1

\tif _player != null and _player is Node2D:
\t\tvar p := (_player as Node2D).global_position
\t\tif not _moved and p.distance_to(_start_pos) > 1.0:
\t\t\t_moved = true
\t\t# A player thousands of units away is falling through the world.
\t\tif abs(p.x) > 100000.0 or abs(p.y) > 100000.0:
\t\t\tprint("RUNTIME_FAIL PLAYER_LOST player left the world at ", p,
\t\t\t\t" - it is falling forever. Check collision shapes and gravity.")
\t\t\tquit(1)
\t\t\treturn true

\tif _frames >= FRAMES:
\t\t_check_content()
\t\t# A player that never moves in 300 frames is inert. With gravity in the
\t\t# world it should at least fall; if it does not, the physics or the script
\t\t# is not wired up and the game has no controls.
\t\tif _player == null:
\t\t\tprint("RUNTIME_FAIL NO_PLAYER no node named like a player exists in the scene.")
\t\telif not _moved and EXPECT.has("platform"):
\t\t\tprint("RUNTIME_FAIL PLAYER_INERT the player never moved in ", FRAMES,
\t\t\t\t" frames. It is not affected by gravity or has no script attached, ",
\t\t\t\t"so the game has no working controls.")
\t\tprint("RUNTIME_OK frames=", _frames, " player_moved=", _moved)
\t\tquit(0)
\t\treturn true
\treturn false

func _check_content() -> void:
\t# The level must actually contain what the plan promised. A scene with an
\t# empty "Enemies" container and no spawner passes every structural gate
\t# while being an empty game.
\tfor role in EXPECT.keys():
\t\tvar want: int = int(EXPECT[role])
\t\tvar found := _count_role(get_root(), ROLE_WORDS[role])
\t\tif found == 0:
\t\t\tprint("RUNTIME_FAIL NO_", String(role).to_upper(),
\t\t\t\t" the level declares ", want, " ", role,
\t\t\t\t" but the running game contains NONE. Either place them in the scene ",
\t\t\t\t"or spawn them in _ready().")
\t\telif found < want / 2:
\t\t\tprint("RUNTIME_FAIL TOO_FEW_", String(role).to_upper(),
\t\t\t\t" the level declares ", want, " ", role, " but only ", found,
\t\t\t\t" exist at runtime.")

func _count_role(n: Node, words: Array) -> int:
\tvar total := 0
\tvar lower := String(n.name).to_lower()
\tfor w in words:
\t\tif lower.contains(String(w)):
\t\t\ttotal += 1
\t\t\tbreak
\tfor c in n.get_children():
\t\ttotal += _count_role(c, words)
\treturn total

func _install_autoloads() -> void:
\t# Mirrors what the engine does for [autoload] entries in project.godot.
\tfor name in AUTOLOADS.keys():
\t\tvar script = load(AUTOLOADS[name])
\t\tif script == null:
\t\t\tprint("RUNTIME_FAIL AUTOLOAD_MISSING ", AUTOLOADS[name], " could not be loaded")
\t\t\tcontinue
\t\tvar node = Node.new()
\t\tnode.set_script(script)
\t\tnode.name = String(name)
\t\tget_root().add_child(node)

func _find_player(n: Node) -> Node:
\tvar name_lower := String(n.name).to_lower()
\tif name_lower.contains("player") and n is Node2D:
\t\treturn n
\tfor c in n.get_children():
\t\tvar found := _find_player(c)
\t\tif found != null:
\t\t\treturn found
\treturn null
'''
