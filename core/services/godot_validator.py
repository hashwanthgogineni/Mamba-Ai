"""
Godot validation gates.

Measured against Godot 4.7.2 — the behaviour here is not what you would guess:

  * `--check-only` exits 0 even on a parse error, so exit codes are useless.
  * A wrong `load_steps` count is silently tolerated.
  * A bad `parent=` path only warns, then builds a node literally named
    "Parent#Child" at the root.
  * Trailing garbage in a .tscn is silently ignored.

So three layers are needed together, and none of them is the exit code:

  1. stderr scan      — catches parse errors and missing ext_resources
  2. orphan assert    — catches vanished parent paths ('#' in a node name)
  3. manifest assert  — catches silently dropped nodes, by requiring every
                        node path the generator declared to actually exist

Exit-time noise ("leaked", "still in use", "RID allocations") appears on
perfectly healthy runs too, so it must be filtered or the gate cries wolf.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Lines Godot prints at exit even when everything is fine.
_EXIT_NOISE = (
    "were leaked",
    "still in use",
    "RID allocation",
    "RIDs of type",
    "ObjectDB instances",
)

# stderr patterns that indicate a genuine problem.
_ERROR_PATTERNS = (
    re.compile(r"SCRIPT ERROR:\s*(?P<msg>.+)"),
    re.compile(r"ERROR:\s*(?P<msg>.+)"),
    re.compile(r"Parse Error:\s*(?P<msg>.+)"),
)

# Pull "res://path/file.ext:LINE" out of an error line when present.
_LOCATION = re.compile(r"(?P<file>res://[^\s:\"]+):(?P<line>\d+)")
# Many Godot errors name the file without a line, e.g.
#   Failed to load script "res://scripts/pickup.gd" with error "Compilation failed".
_ANY_RES_PATH = re.compile(r"res://(?P<file>[A-Za-z0-9_\-/.]+\.(?:gd|tscn|tres))")


@dataclass
class Issue:
    """A single problem, addressed to one file so repair can be targeted."""
    file: str
    message: str
    line: Optional[int] = None
    kind: str = "error"

    def as_prompt_line(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        return f"- {self.file}{loc}: {self.message}"


# Failures that mean the result is not a playable game. Anything else is worth
# reporting but not worth refusing to ship over.
BLOCKING_MARKERS = (
    "NO_SCRIPT", "PLAYER_INERT", "NO_PLAYER", "NO_VISUAL",
    "LOAD_FAILED", "INSTANTIATE_FAILED", "MISSING_NODE",
    "NO_ENEMY", "NO_COLLECTIBLE", "NO_PLATFORM",
    "TOO_FEW_ENEMY", "TOO_FEW_COLLECTIBLE", "TOO_FEW_PLATFORM",
    "Parse Error", "Compile Error", "Failed to load script",
)


def is_blocking(issue: "Issue") -> bool:
    return any(marker in issue.message for marker in BLOCKING_MARKERS)


@dataclass
class ValidationResult:
    ok: bool
    issues: List[Issue] = field(default_factory=list)
    raw: str = ""

    def blocking(self) -> List[Issue]:
        """Issues that make the output not-a-game."""
        return [i for i in self.issues if is_blocking(i)]

    def by_file(self) -> Dict[str, List[Issue]]:
        out: Dict[str, List[Issue]] = {}
        for issue in self.issues:
            out.setdefault(issue.file, []).append(issue)
        return out


class GodotValidator:
    def __init__(self, godot_path: str = "godot", timeout: int = 180):
        self.godot = godot_path
        self.timeout = timeout

    async def _run(self, project: Path, *args: str) -> tuple[int, str]:
        """Run godot headless against a project, returning (code, stdout+stderr)."""
        cmd = [self.godot, "--headless", "--path", str(project), *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            return proc.returncode or 0, out.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            logger.error(f"Godot timed out after {self.timeout}s: {' '.join(args)}")
            return 1, f"TIMEOUT after {self.timeout}s running: {' '.join(args)}"
        except FileNotFoundError:
            raise RuntimeError(
                f"Godot not found at '{self.godot}'. Install it or set GODOT_PATH."
            )

    # ---------- layer 1 ----------

    def _scan_stderr(self, text: str, default_file: str = "project") -> List[Issue]:
        issues: List[Issue] = []
        seen: set = set()

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or any(noise in line for noise in _EXIT_NOISE):
                continue
            # Our own gate output is handled separately.
            if line.startswith("GATE_"):
                continue

            for pattern in _ERROR_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                message = match.group("msg").strip()
                location = _LOCATION.search(line)
                target = default_file
                lineno = None
                if location:
                    target = location.group("file").replace("res://", "")
                    lineno = int(location.group("line"))
                else:
                    # No line number, but the message may still name the file.
                    named = _ANY_RES_PATH.search(line)
                    if named and "validate.gd" not in named.group("file"):
                        target = named.group("file")
                key = (target, message)
                if key in seen:
                    break
                seen.add(key)
                issues.append(Issue(file=target, message=message, line=lineno))
                break

        return issues

    # ---------- gates ----------

    async def import_project(self, project: Path) -> ValidationResult:
        """Resources must be imported or they never enter the exported .pck."""
        _, out = await self._run(project, "--import")
        issues = self._scan_stderr(out)
        return ValidationResult(ok=not issues, issues=issues, raw=out)

    async def check_scripts(
        self,
        project: Path,
        scripts: List[str],
        autoloads: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Parse each GDScript file. Exit code is meaningless; read the output.

        `--check-only` parses a script in isolation and does NOT resolve autoload
        singletons, so a correct `GameManager.add_score()` is reported as
        "Identifier not found: GameManager". Those are false positives — left in,
        they make the repair stage rewrite working code into defensive junk.
        """
        autoloads = autoloads or []
        all_issues: List[Issue] = []
        combined = []

        for rel in scripts:
            _, out = await self._run(project, "--check-only", "--script", f"res://{rel}")
            combined.append(out)
            issues = [
                i for i in self._scan_stderr(out, default_file=rel)
                if not self._is_autoload_false_positive(i, autoloads)
            ]
            # "Compilation failed" is only a symptom; drop it if its cause was filtered.
            if all("Compilation failed" in i.message for i in issues) and issues:
                issues = []
            for issue in issues:
                issue.file = issue.file or rel
                all_issues.append(issue)

        return ValidationResult(ok=not all_issues, issues=all_issues, raw="\n".join(combined))

    @staticmethod
    def _is_autoload_false_positive(issue: "Issue", autoloads: List[str]) -> bool:
        for name in autoloads:
            if f"Identifier not found: {name}" in issue.message:
                logger.debug(f"Ignoring autoload false positive for '{name}'")
                return True
        return False

    async def check_scenes(self, project: Path, expected: Dict[str, List[str]]) -> ValidationResult:
        """
        Layers 2 and 3. `expected` maps a scene path to the node paths the
        generator declared, e.g. {"scenes/Main.tscn": ["Player", "Player/Shape"]}.
        """
        harness = _VALIDATE_GD.replace("__EXPECTED_JSON__", json.dumps(expected))
        (project / "validate.gd").write_text(harness, encoding="utf-8")

        _, out = await self._run(project, "--script", "res://validate.gd")

        # A scene-load error that names no file is almost always a problem with
        # the scene itself (wrong script on a node, bad resource), so attribute
        # it there rather than to an unrepairable "project" bucket.
        fallback = next(iter(expected), "project") if len(expected) == 1 else "project"
        issues = self._scan_stderr(out, default_file=fallback)
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("GATE_FAIL"):
                continue
            payload = line[len("GATE_FAIL"):].strip()
            kind, _, rest = payload.partition(" ")
            scene, _, detail = rest.partition(" ")
            issues.append(Issue(
                file=scene.replace("res://", "") or "scene",
                message=f"{kind}: {detail}".strip(": ").strip(),
                kind="structure",
            ))

        return ValidationResult(ok=not issues, issues=issues, raw=out)

    async def validate_all(
        self,
        project: Path,
        scripts: List[str],
        expected_scenes: Dict[str, List[str]],
        autoloads: Optional[List[str]] = None,
    ) -> ValidationResult:
        """Run every gate, collecting issues rather than stopping at the first."""
        issues: List[Issue] = []
        raw: List[str] = []

        autoloads = autoloads or []
        for result in (
            await self.import_project(project),
            await self.check_scripts(project, scripts, autoloads),
            await self.check_scenes(project, expected_scenes),
        ):
            # Autoload singletons are unresolved in every headless parse context,
            # not just --check-only, so the filter belongs here too.
            issues.extend(
                i for i in result.issues
                if not self._is_autoload_false_positive(i, autoloads)
            )
            raw.append(result.raw)

        # "Compilation failed" is a symptom; drop it when its cause was filtered.
        causes = {i.file for i in issues if "Compilation failed" not in i.message}
        issues = [
            i for i in issues
            if "Compilation failed" not in i.message or i.file in causes
        ]

        # Deduplicate: the same parse error surfaces in more than one gate.
        unique: List[Issue] = []
        seen: set = set()
        for issue in issues:
            key = (issue.file, issue.message)
            if key not in seen:
                seen.add(key)
                unique.append(issue)

        if unique:
            logger.warning(f"Godot validation found {len(unique)} issue(s)")
            for issue in unique[:8]:
                logger.warning(f"   {issue.as_prompt_line()}")
        else:
            logger.info("✅ Godot validation passed all gates")

        return ValidationResult(ok=not unique, issues=unique, raw="\n".join(raw))


# Harness run inside Godot. __EXPECTED_JSON__ is substituted before writing.
_VALIDATE_GD = '''extends SceneTree
# Generated by godot_validator.py — do not edit by hand.
# Godot tolerates broken scenes silently, so assert explicitly.

const EXPECTED := __EXPECTED_JSON__

func _init() -> void:
\tvar failures := 0
\tfor scene_path in EXPECTED.keys():
\t\tvar res_path: String = "res://" + str(scene_path)
\t\tvar packed = load(res_path)
\t\tif packed == null:
\t\t\tprint("GATE_FAIL LOAD_FAILED ", res_path, " scene could not be loaded")
\t\t\tfailures += 1
\t\t\tcontinue
\t\tvar inst = packed.instantiate()
\t\tif inst == null:
\t\t\tprint("GATE_FAIL INSTANTIATE_FAILED ", res_path, " scene could not be instantiated")
\t\t\tfailures += 1
\t\t\tcontinue
\t\tfailures += _check_orphans(inst, res_path)
\t\tfailures += _check_visible(inst, res_path)
\t\tfailures += _check_scripted(inst, res_path)
\t\tfor node_path in EXPECTED[scene_path]:
\t\t\tif inst.get_node_or_null(NodePath(node_path)) == null:
\t\t\t\tprint("GATE_FAIL MISSING_NODE ", res_path, " declared node '", node_path, "' is not in the built tree")
\t\t\t\tfailures += 1
\t\tinst.free()
\tprint("GATE_RESULT failures=", failures)
\tquit(1 if failures > 0 else 0)

# An entity scene whose root is a physics body but which draws nothing is
# structurally valid and completely invisible in game. Godot never complains.
# Only the ROOT is checked: child Area2D triggers legitimately have no visual.
const DRAWABLE := ["Polygon2D", "Sprite2D", "AnimatedSprite2D", "ColorRect",
\t"TextureRect", "Line2D", "Label", "MeshInstance2D", "TileMapLayer", "TileMap"]
const BODY := ["CharacterBody2D", "StaticBody2D", "RigidBody2D", "Area2D"]

func _check_visible(root: Node, scene: String) -> int:
\tif not (root.get_class() in BODY):
\t\treturn 0
\tif _has_drawable(root):
\t\treturn 0
\tprint("GATE_FAIL NO_VISUAL ", scene, " root '", root.name, "' (", root.get_class(),
\t\t") draws nothing - add a Polygon2D or Sprite2D child or it is invisible in game")
\treturn 1

func _has_drawable(n: Node) -> bool:
\tif n.get_class() in DRAWABLE:
\t\treturn true
\tfor c in n.get_children():
\t\tif _has_drawable(c):
\t\t\treturn true
\treturn false

# A CharacterBody2D with no script attached cannot move, jump or respond to
# input. It loads and instantiates perfectly and throws nothing at runtime, so
# no other gate notices that the game has no controls.
const NEEDS_SCRIPT := ["CharacterBody2D", "RigidBody2D"]

func _check_scripted(root: Node, scene: String) -> int:
\tvar failures := 0
\tfor n in _all_nodes(root):
\t\tif n.get_class() in NEEDS_SCRIPT and n.get_script() == null:
\t\t\tprint("GATE_FAIL NO_SCRIPT ", scene, " node '", n.name, "' (", n.get_class(),
\t\t\t\t") has no script attached, so it cannot move or respond to input. ",
\t\t\t\t"Attach one with script = ExtResource(...).")
\t\t\tfailures += 1
\treturn failures

func _all_nodes(n: Node) -> Array:
\tvar out := [n]
\tfor c in n.get_children():
\t\tout += _all_nodes(c)
\treturn out

func _check_orphans(n: Node, scene: String) -> int:
\tvar found := 0
\tif "#" in String(n.name):
\t\tprint("GATE_FAIL ORPHAN_NODE ", scene, " node '", n.name, "' has a parent= path that does not exist")
\t\tfound += 1
\tfor c in n.get_children():
\t\tfound += _check_orphans(c, scene)
\treturn found
'''
