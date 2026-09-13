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

# Genres where a player node must exist. A puzzle board has none by design.
_HAS_PLAYER = {"platformer", "maze", "shooter", "runner", "topdown"}

# Genres where the player must visibly move with no input at all. Only the
# platformer qualifies: it spawns above ground and gravity pulls it down, so a
# motionless player there means physics or the script is not wired up.
#
# A runner's player stands on the ground and only jumps — the WORLD scrolls, not
# the player. A shooter or top-down player moves on input alone. Asserting
# motion in those is a false failure, and false failures make the repair loop
# rewrite working code.
_HAS_GRAVITY = {"platformer"}

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


def _with_probe_autoload(project_godot: str) -> str:
    """Add the probe as an autoload for the duration of one test run."""
    line = 'MambaProbe="*res://mamba_probe.gd"'
    if line in project_godot:
        return project_godot
    if "[autoload]" in project_godot:
        return project_godot.replace("[autoload]\n", "[autoload]\n\n" + line + "\n", 1)
    return project_godot.rstrip("\n") + "\n\n[autoload]\n\n" + line + "\n"


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
        genre: str = "platformer",
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
        # Run the REAL game, not a SceneTree script.
        #
        # A `--script` run does not register autoload singletons, so any script
        # referencing `GameManager` fails to compile — a false failure produced
        # entirely by the harness. `--quit-after` boots the project properly,
        # autoloads and all, and the probe rides along as an extra autoload so
        # its assertions run inside the real game.
        probe = (
            _PROBE_GD
            .replace("__FRAMES__", str(frames))
            .replace("__EXPECT__", json.dumps(expect or {}))
            .replace("__ROLE_WORDS__", json.dumps(_ROLE_WORDS))
            .replace("__EXPECT_PLAYER__", "true" if genre in _HAS_PLAYER else "false")
            .replace("__EXPECT_MOTION__", "true" if genre in _HAS_GRAVITY else "false")
        )
        (project / "mamba_probe.gd").write_text(probe, encoding="utf-8")

        project_file = project / "project.godot"
        original = project_file.read_text(encoding="utf-8")
        patched = _with_probe_autoload(original)
        project_file.write_text(patched, encoding="utf-8")

        cmd = [
            self.godot, "--headless", "--path", str(project.resolve()),
            "--quit-after", str(frames + 60),
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
            project_file.write_text(original, encoding="utf-8")
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

        project_file.write_text(original, encoding="utf-8")

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
            if message.startswith("Parse Error") and "mamba_probe.gd" in line:
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

            if "mamba_probe.gd" in target:
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
_PROBE_GD = '''extends Node
# Generated by godot_runtime.py — do not edit by hand.
# Runs as an autoload inside the REAL game, so singletons, _ready() and physics
# all behave exactly as they do for a player. A --script SceneTree run does not
# register autoloads and reports false compile failures instead.

const FRAMES := __FRAMES__
const EXPECT := __EXPECT__
const ROLE_WORDS := __ROLE_WORDS__
const EXPECT_PLAYER := __EXPECT_PLAYER__
const EXPECT_MOTION := __EXPECT_MOTION__

var _frames := 0
var _player: Node2D = null
var _start := Vector2.ZERO
var _moved := false
var _done := false


func _ready() -> void:
	process_priority = 1000


func _process(_delta: float) -> void:
	if _done:
		return
	_frames += 1

	if _player == null or not is_instance_valid(_player):
		_player = _find_player(get_tree().root)
		if _player != null:
			_start = _player.global_position

	if _player != null:
		var p := _player.global_position
		if not _moved and p.distance_to(_start) > 1.0:
			_moved = true
		if absf(p.x) > 100000.0 or absf(p.y) > 100000.0:
			print("RUNTIME_FAIL PLAYER_LOST player left the world at ", p,
				" - it is falling forever. Check collision shapes and gravity.")
			_finish()
			return

	if _frames >= FRAMES:
		_finish()


func _finish() -> void:
	_done = true
	_check_content()
	if _player == null:
		if EXPECT_PLAYER:
			print("RUNTIME_FAIL NO_PLAYER no node named like a player exists in the scene.")
	elif not _moved and EXPECT_MOTION:
		print("RUNTIME_FAIL PLAYER_INERT the player never moved in ", FRAMES,
			" frames. It is not affected by gravity and does not respond to input, ",
			"so the game has no working controls.")
	print("RUNTIME_OK frames=", _frames, " player_moved=", _moved)


func _check_content() -> void:
	# The level must contain what the plan promised. An empty container with no
	# spawner passes every structural gate while being an empty game.
	for role in EXPECT.keys():
		var want: int = int(EXPECT[role])
		var found := _count_role(get_tree().root, ROLE_WORDS[role])
		if found == 0:
			print("RUNTIME_FAIL NO_", String(role).to_upper(),
				" the level declares ", want, " ", role,
				" but the running game contains NONE.")
		elif found * 2 < want:
			print("RUNTIME_FAIL TOO_FEW_", String(role).to_upper(),
				" the level declares ", want, " ", role, " but only ", found,
				" exist at runtime.")


func _count_role(n: Node, words: Array) -> int:
	var total := 0
	var lower := String(n.name).to_lower()
	for w in words:
		if lower.contains(String(w)):
			total += 1
			break
	for c in n.get_children():
		total += _count_role(c, words)
	return total


func _find_player(n: Node) -> Node2D:
	if n is Node2D and String(n.name).to_lower().contains("player"):
		return n as Node2D
	for c in n.get_children():
		var found := _find_player(c)
		if found != null:
			return found
	return null
'''
