"""
AI generation of Godot project content.

Two stages:
  1. plan   — one call, returns the game design plus the file manifest,
              including the node paths each scene promises to contain
  2. files  — one call per file, run concurrently, each given the plan plus
              format rules for its file type

Repair is per file, not per project: Godot reports the failing file and line,
so only that file is regenerated. Regenerating everything is slower and risks
breaking files that already pass.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


TSCN_RULES = """
GODOT 4 .tscn FORMAT — follow exactly:

[gd_scene load_steps=N format=3]

[ext_resource type="Script" path="res://scripts/player.gd" id="1_player"]

[sub_resource type="RectangleShape2D" id="RectangleShape2D_a"]
size = Vector2(32, 48)

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
position = Vector2(200, 400)
script = ExtResource("1_player")

[node name="Shape" type="CollisionShape2D" parent="Player"]
shape = SubResource("RectangleShape2D_a")

SCENES STAY SMALL — THIS IS THE MOST IMPORTANT RULE:
- Main.tscn must contain ONLY: the root node, a few empty container nodes
  (Platforms, Enemies, Collectibles), the player, and the HUD. Roughly 8-12
  nodes TOTAL, never more.
- NEVER write one [node] block per platform, per enemy or per collectible. A
  scene with 30 hand-written nodes means 30 hand-counted resource ids and a
  load_steps total that is wrong more often than right.
- The level content is SPAWNED IN CODE instead, by the level script, from
  constants that mirror the plan's level data:

      const PLATFORMS := [[0, 600, 1152, 48], [180, 500, 160, 24]]

      func _ready() -> void:
          for p in PLATFORMS:
              _spawn_platform(p[0], p[1], p[2], p[3])

  That is loops doing arithmetic, which is reliable, instead of you doing
  arithmetic by hand, which is not.
- Reusable things (Player, Enemy, Coin) are their own small .tscn files,
  instanced in code with preload("res://scenes/Enemy.tscn").instantiate().

HARD RULES:
- format=3 always.
- load_steps = (number of ext_resource) + (number of sub_resource) + 1.
- The FIRST [node] has NO parent attribute. It is the scene root.
- Every other node MUST have parent="." (direct child of root) or
  parent="NodeName" / parent="NodeName/ChildName" naming an EARLIER node.
  A parent path that does not exist silently breaks the scene.
- Reference resources only by ids you declared: ExtResource("id"), SubResource("id").
- Every ext_resource path must be a file that exists in this project.
- Colors are Color(r, g, b, a) with floats 0..1.
- Prefer Sprite2D with a texture from the sprite list below. Use Polygon2D
  only for things no sprite exists for (backgrounds, simple bars).
  Never reference a texture path that is not in that list.
- A CollisionShape2D needs a `shape = SubResource(...)`.
- EVERY entity scene (player, enemy, pickup) MUST include a visible child node —
  a Polygon2D or Sprite2D. A body with only a CollisionShape2D is INVISIBLE in
  the running game even though the scene loads fine. This is checked.
- Physics bodies: CharacterBody2D (player), StaticBody2D (platforms),
  Area2D (pickups, hazards).
- Output ONLY the file contents. No markdown fences, no commentary.
"""

GDSCRIPT_RULES = """
GODOT 4 GDScript RULES — follow exactly:

- Indent with TABS only. Never spaces. Mixed indentation is a parse error.
- First line is `extends <NodeType>`.
- Godot 4 API (NOT Godot 3):
    velocity is a built-in property on CharacterBody2D
    move_and_slide()          takes NO arguments
    is_on_floor()             no arguments
    Input.get_axis("neg", "pos")
    Input.is_action_just_pressed("name")
    @onready var x = $NodePath
    @export var speed: float = 300.0
    func _physics_process(delta: float) -> void:
    signals: signal died   /   emit:  died.emit()
    get_tree().reload_current_scene()
- Only reference input actions that exist: ui_left, ui_right, ui_up, ui_down,
  ui_accept, ui_cancel — these are built in and always available.
- Only use $NodePath for nodes that exist in the scene this script is attached to.
- THE LEVEL SCRIPT BUILDS THE LEVEL. Put the plan's level data in constants at
  the top of the file, then spawn every platform, enemy and collectible in
  _ready() by looping over them and adding children to the container nodes.
  Never expect them to already exist in the scene.
- When spawning something visual, give it a Sprite2D with a texture from the
  sprite list, a CollisionShape2D with a real shape, and add it to the right
  container. A spawned body with no sprite is invisible; with no shape it has
  no collision.
- Do not reference other scripts' members unless they are autoload singletons.
- Output ONLY the file contents. No markdown fences, no commentary.
"""

PLAN_SCHEMA = """{
  "title": "short game title",
  "description": "one sentence",
  "window": {"width": 1152, "height": 648},
  "main_scene": "scenes/Main.tscn",
  "palette": {"background": "#101014", "player": "#25D366", "enemy": "#E8705F",
              "platform": "#3A3A45", "collectible": "#F2C94C"},
  "mechanics": {"speed": 300.0, "jump_velocity": -450.0, "gravity": 980.0,
                "max_fall_speed": 900.0, "enemy_speed": 80.0},
  "level": {
    "spawn": [120, 420],
    "platforms": [[0, 600, 1152, 48], [300, 470, 200, 24]],
    "enemies": [[600, 430]],
    "collectibles": [[340, 420], [700, 300]],
    "goal": [1050, 540]
  },
  "autoloads": {"GameManager": "scripts/game_manager.gd"},
  "scripts": [
    {"path": "scripts/game_manager.gd", "extends": "Node",
     "purpose": "score, win/lose state, restart"},
    {"path": "scripts/player.gd", "extends": "CharacterBody2D",
     "purpose": "movement, jump, gravity"}
  ],
  "scenes": [
    {"path": "scenes/Main.tscn", "root_type": "Node2D",
     "purpose": "world, platforms, player, enemies, collectibles",
     "nodes": ["Player", "Player/Shape", "Ground", "Ground/Shape"]}
  ]
}"""


def _strip_fences(text: str) -> str:
    """Remove markdown fences the model adds despite being told not to."""
    if not text:
        return ""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_json(text: str) -> Optional[Dict]:
    text = _strip_fences(text)
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # One repair pass: strip trailing commas.
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None


class AIGodotGenerator:
    def __init__(self, deepseek_client, max_parallel: int = 4):
        self.ai = deepseek_client
        # role -> 'assets/x.png', set once the sprites are on disk
        self.sprites: Dict[str, str] = {}
        self._sem = asyncio.Semaphore(max_parallel)

    # ---------- stage 1 ----------

    async def generate_plan(
        self,
        user_prompt: str,
        attempts: int = 3,
        genre_id: str = None,
        brief: str = None,
    ) -> Dict[str, Any]:
        """
        `genre_id` selects the level/mechanics schema. Using one platformer
        schema for every genre is what turns a Pac-Man request into floating
        blocks: "maze corridors" has nowhere to live in platforms[].
        """
        from services import game_genres

        genre = game_genres.get(genre_id)
        schema = game_genres.plan_schema(genre)
        rules = game_genres.rules_block(genre)
        request = brief or f'"{user_prompt}"'

        messages = [
            {
                "role": "system",
                "content": f"You are a senior Godot 4 game designer specialising in "
                           f"{genre.label} games. You reply with JSON only."
            },
            {
                "role": "user",
                "content": f"""Design a complete, playable Godot 4 2D game from this request:

{request}

{rules}

Return JSON matching this shape exactly:

{schema}

REQUIREMENTS:
- Every script in "scripts" must be referenced by a scene or be an autoload.
- "nodes" lists the node paths that scene MUST contain, relative to its root.
  These are verified after generation, so list only nodes you will create.
- Build a COMPLETE, DENSE level — a real game, not a demo. Fill the play area.
  A sparse level with three platforms is a failure, not a safe choice.
- Use as many scripts and scenes as the game genuinely needs (typically 3-6
  scripts, 2-4 scenes). Never pad, but never under-build either.
- Coordinates must fit inside the window size you choose.
- Platforms are [x, y, width, height]. Positions are [x, y].
- The player spawn must be above a platform, not inside it.

Return ONLY the JSON object."""
            }
        ]

        last_error = "no response"
        for attempt in range(attempts):
            # Thinking mode spends part of the budget reasoning before answering,
            # and the level examples are large, so the plan needs real headroom.
            # If the budget is still exhausted, fall back to no-thinking: a plan
            # is structured data, and getting one beats getting nothing.
            try:
                response = await self.ai.generate(
                    messages, temperature=0.3, max_tokens=64000,
                    thinking=(attempt == 0),
                )
            except ValueError as e:
                if "ran out of tokens" not in str(e):
                    raise
                logger.warning("Plan exhausted its budget while reasoning; retrying without thinking")
                response = await self.ai.generate(
                    messages, temperature=0.3, max_tokens=64000, thinking=False
                )
            plan = _parse_json(response.get("content", ""))
            if plan and plan.get("scenes") and plan.get("scripts"):
                logger.info(
                    f"📋 Plan: '{plan.get('title')}' "
                    f"{len(plan.get('scenes', []))} scene(s), "
                    f"{len(plan.get('scripts', []))} script(s)"
                )
                return plan
            last_error = "missing scenes/scripts" if plan else "unparseable JSON"
            logger.warning(f"Plan attempt {attempt + 1} failed: {last_error}")
            messages.append({"role": "user", "content":
                             f"That failed: {last_error}. Return ONLY valid JSON matching the schema."})

        raise ValueError(f"Could not produce a valid game plan: {last_error}")

    # ---------- stage 2 ----------

    def _file_prompt(self, plan: Dict, path: str, spec: Dict) -> str:
        rules = TSCN_RULES if path.endswith(".tscn") else GDSCRIPT_RULES
        from services import game_genres
        genre = game_genres.get(plan.get("genre"))

        context = {
            "title": plan.get("title"),
            "palette": plan.get("palette"),
            "mechanics": plan.get("mechanics"),
            "level": plan.get("level"),
            "genre": plan.get("genre"),
            "scripts": [s.get("path") for s in plan.get("scripts", [])],
            "scenes": [s.get("path") for s in plan.get("scenes", [])],
            "autoloads": plan.get("autoloads"),
        }

        extra = ""
        if path.endswith(".tscn"):
            required = spec.get("nodes") or []
            extra = (
                f"\nThis scene MUST contain these node paths exactly "
                f"(they are verified after generation):\n{json.dumps(required, indent=2)}\n"
                f"Root node type: {spec.get('root_type', 'Node2D')}\n"
                "Keep it SMALL: containers, the player and the HUD only. The "
                "level script fills the containers at runtime — do NOT place one "
                "node per platform, enemy or collectible here."
            )
        else:
            extra = (
                f"\nThis script extends {spec.get('extends', 'Node')}.\n"
                f"Purpose: {spec.get('purpose', '')}\n"
                "Use the exact numbers from `mechanics` as constants."
            )

        from services.asset_library import manifest_block

        return f"""Write the file `{path}` for this Godot 4 game.

{game_genres.rules_block(genre)}

{manifest_block(self.sprites)}

GAME CONTEXT:
{json.dumps(context, indent=2)}
{extra}
{rules}"""

    async def _generate_one(self, plan: Dict, path: str, spec: Dict) -> tuple[str, str]:
        async with self._sem:
            logger.info(f"   ✍️  generating {path}")
            response = await self.ai.generate(
                [{"role": "user", "content": self._file_prompt(plan, path, spec)}],
                temperature=0.15,
                # A level-building script or a scene with many nodes is long,
                # and thinking mode spends part of this budget before writing
                # anything. 32k was not enough in practice.
                max_tokens=64000,
            )
            return path, _strip_fences(response.get("content", ""))

    async def generate_files(self, plan: Dict) -> Dict[str, str]:
        """Generate every scene and script concurrently (no per-file checking)."""
        tasks = []
        for scene in plan.get("scenes", []):
            if scene.get("path"):
                tasks.append(self._generate_one(plan, scene["path"], scene))
        for script in plan.get("scripts", []):
            if script.get("path"):
                tasks.append(self._generate_one(plan, script["path"], script))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        files: Dict[str, str] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"File generation failed: {result}")
                continue
            path, content = result
            if content:
                files[path] = content
            else:
                logger.error(f"Empty content generated for {path}")

        logger.info(f"📝 Generated {len(files)} file(s)")
        return files

    async def generate_checked(
        self,
        plan: Dict,
        path: str,
        spec: Dict,
        checker,
        max_fixes: int = 3,
    ) -> tuple[str, str, List[str]]:
        """
        Generate one file and do not return until it passes its own checks
        (or the fix budget runs out).

        `checker` is an async callable taking (path, content) and returning a
        list of problem strings. Files stay concurrent with each other — each
        one just loops on itself until green.
        """
        path, content = await self._generate_one(plan, path, spec)
        if not content:
            return path, content, ["Generation produced an empty file"]

        for attempt in range(max_fixes + 1):
            problems = await checker(path, content)
            if not problems:
                if attempt:
                    logger.info(f"   ✅ {path} green after {attempt} fix(es)")
                return path, content, []
            if attempt == max_fixes:
                logger.warning(f"   ⚠️  {path} still has {len(problems)} issue(s) after {max_fixes} fix(es)")
                return path, content, problems

            logger.info(f"   🔁 {path}: {len(problems)} issue(s), fixing in place")
            fixed = await self.repair_file(plan, path, spec, content, problems)
            if not fixed:
                return path, content, problems
            content = fixed

        return path, content, []

    # ---------- iteration ----------

    async def plan_edit(
        self,
        plan: Dict,
        change_request: str,
        current: Dict[str, str],
    ) -> List[str]:
        """Decide which existing files need to change. Returns paths only."""
        inventory = "\n".join(
            f"  {path} ({len(content.splitlines())} lines)"
            for path, content in current.items()
        )
        prompt = f"""An existing Godot 4 game needs a change.

THE GAME:
{json.dumps({k: plan.get(k) for k in ("title", "genre", "mechanics", "level")}, indent=2)[:3000]}

FILES IN THE PROJECT:
{inventory}

THE USER ASKS:
"{change_request}"

Which files must be modified to satisfy this? Change as FEW as possible —
files you do not list are left untouched.

Return JSON only:
{{"files": ["scripts/player.gd"], "reason": "one short sentence"}}"""

        try:
            response = await self.ai.generate(
                [{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=8000, thinking=False,
            )
            data = _parse_json(response.get("content", "")) or {}
        except Exception as e:
            logger.warning(f"plan_edit failed: {e}")
            return []

        wanted = [f for f in (data.get("files") or []) if f in current]
        if data.get("reason"):
            logger.info(f"✏️  Edit plan: {data['reason']} -> {wanted}")
        return wanted[:6]

    async def edit_file(
        self,
        plan: Dict,
        path: str,
        spec: Dict,
        current: str,
        change_request: str,
        checker,
        max_fixes: int = 2,
    ) -> Optional[str]:
        """Rewrite one existing file to satisfy the change, then check it."""
        from services import game_genres

        genre = game_genres.get(plan.get("genre"))
        rules = TSCN_RULES if path.endswith(".tscn") else GDSCRIPT_RULES

        from services.asset_library import manifest_block

        prompt = f"""Modify the existing file `{path}` in this Godot 4 game.

{game_genres.rules_block(genre)}

{manifest_block(self.sprites)}

GAME CONTEXT:
{json.dumps({k: plan.get(k) for k in ("title", "genre", "palette", "mechanics", "level")}, indent=2)[:4000]}

CURRENT CONTENT OF {path}:
{current}

THE USER ASKS:
"{change_request}"

Apply that change. Keep everything else working — this file is part of a game
that currently runs. Do not rewrite it from scratch; modify what is there.

{rules}"""

        async with self._sem:
            logger.info(f"   ✏️  editing {path}")
            response = await self.ai.generate(
                [{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=64000,
            )
        content = _strip_fences(response.get("content", ""))
        if not content:
            return None

        for attempt in range(max_fixes + 1):
            problems = await checker(path, content)
            if not problems:
                return content
            if attempt == max_fixes:
                logger.warning(f"   ⚠️  {path} edited but still has {len(problems)} issue(s)")
                return content
            fixed = await self.repair_file(plan, path, spec, content, problems)
            if not fixed:
                return content
            content = fixed

        return content

    # ---------- repair ----------

    async def repair_file(
        self,
        plan: Dict,
        path: str,
        spec: Dict,
        current: str,
        issues: List[str],
    ) -> Optional[str]:
        """Regenerate one file, given Godot's own error output."""
        rules = TSCN_RULES if path.endswith(".tscn") else GDSCRIPT_RULES
        problems = "\n".join(issues)

        prompt = f"""The file `{path}` fails validation in Godot 4.

GODOT REPORTED:
{problems}

CURRENT CONTENT:
{current}

{rules}

Fix every reported problem. Change as little else as possible.
Output ONLY the corrected file contents."""

        async with self._sem:
            logger.info(f"   🔧 repairing {path} ({len(issues)} issue(s))")
            # A repair prompt carries the whole failing file plus the error
            # list, so it needs more headroom than a first draft.
            # A repair is mechanical — the exact error and the exact file are
            # both supplied. Reasoning costs tokens here without buying accuracy.
            response = await self.ai.generate(
                [{"role": "user", "content": prompt}],
                temperature=0.05,
                max_tokens=64000,
                thinking=False,
            )
        fixed = _strip_fences(response.get("content", ""))
        return fixed or None
