"""
Scene emitter — code writes every .tscn, the AI writes none.

Rationale, from measurement rather than taste. Across eleven generated games:

    project.godot / export_presets.cfg (templated)   0 failures
    hand-written .tscn with ~30 entity nodes         187 issues in one file

Entity scenes are completely formulaic — a body, a sprite, a collision shape and
a script. There is no creative decision in any of it, only bookkeeping: counting
`load_steps`, assigning resource ids, keeping parent paths consistent. That is
arithmetic, and arithmetic belongs in code.

Emitting them here makes five whole bug classes impossible rather than merely
detectable:

    wrong load_steps   code counts
    bad resource ids   code assigns
    MISSING_NODE       code builds exactly what the plan declares
    NO_VISUAL          the template always includes a sprite
    NO_SCRIPT          the template always attaches one

The AI is left writing only .gd files: movement, enemy behaviour, scoring,
level layout. Actual game logic.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """One reusable game object: its scene, script and art."""
    name: str            # "Player"       -> scenes/Player.tscn
    body: str            # CharacterBody2D | Area2D | StaticBody2D
    script: str          # scripts/player.gd
    sprite_role: str     # key into the sprite manifest
    shape: str = "rect"  # rect | circle
    size: tuple = (48, 48)
    group: str = ""      # added via add_to_group by the spawner


# Which entities each genre needs. The AI writes the matching scripts; the
# scenes are emitted from this.
GENRE_ENTITIES: Dict[str, List[Entity]] = {
    "platformer": [
        Entity("Player", "CharacterBody2D", "scripts/player.gd", "player", "rect", (48, 64), "player"),
        Entity("Enemy", "CharacterBody2D", "scripts/enemy.gd", "enemy", "rect", (48, 48), "enemies"),
        Entity("Collectible", "Area2D", "scripts/collectible.gd", "collectible", "circle", (32, 32), "collectibles"),
    ],
    "maze": [
        Entity("Player", "CharacterBody2D", "scripts/player.gd", "player", "rect", (28, 28), "player"),
        Entity("Enemy", "CharacterBody2D", "scripts/enemy.gd", "enemy", "rect", (28, 28), "enemies"),
        Entity("Collectible", "Area2D", "scripts/collectible.gd", "collectible", "circle", (16, 16), "collectibles"),
    ],
    "shooter": [
        Entity("Player", "CharacterBody2D", "scripts/player.gd", "player", "rect", (48, 48), "player"),
        Entity("Enemy", "Area2D", "scripts/enemy.gd", "enemy", "rect", (44, 44), "enemies"),
        Entity("Bullet", "Area2D", "scripts/bullet.gd", "bullet", "rect", (10, 26), "bullets"),
    ],
    "runner": [
        Entity("Player", "CharacterBody2D", "scripts/player.gd", "player", "rect", (48, 64), "player"),
        Entity("Obstacle", "Area2D", "scripts/obstacle.gd", "obstacle", "rect", (48, 48), "obstacles"),
        Entity("Collectible", "Area2D", "scripts/collectible.gd", "collectible", "circle", (32, 32), "collectibles"),
    ],
    "topdown": [
        Entity("Player", "CharacterBody2D", "scripts/player.gd", "player", "rect", (40, 40), "player"),
        Entity("Enemy", "CharacterBody2D", "scripts/enemy.gd", "enemy", "rect", (40, 40), "enemies"),
        Entity("Collectible", "Area2D", "scripts/collectible.gd", "collectible", "circle", (28, 28), "collectibles"),
    ],
    "puzzle": [
        Entity("Tile", "Area2D", "scripts/tile.gd", "tile_a", "rect", (60, 60), "tiles"),
    ],
}

# Containers the level script spawns into. Their names are a contract: the
# generated main.gd looks them up, so they are the one set of node names still
# worth asserting.
CONTAINERS = ["Platforms", "Enemies", "Collectibles", "Projectiles"]


def entities_for(genre_id: str) -> List[Entity]:
    return GENRE_ENTITIES.get(genre_id, GENRE_ENTITIES["platformer"])


def _shape_block(entity: Entity, rid: str) -> str:
    w, h = entity.size
    if entity.shape == "circle":
        return f'[sub_resource type="CircleShape2D" id="{rid}"]\nradius = {max(w, h) / 2:.1f}\n'
    return f'[sub_resource type="RectangleShape2D" id="{rid}"]\nsize = Vector2({w}, {h})\n'


def emit_entity_scene(entity: Entity, sprites: Dict[str, str]) -> str:
    """
    One body + sprite + collision shape + script. load_steps is computed, so
    it cannot be wrong.
    """
    ext: List[str] = [
        f'[ext_resource type="Script" path="res://{entity.script}" id="1_script"]'
    ]
    texture = sprites.get(entity.sprite_role)
    if texture:
        ext.append(f'[ext_resource type="Texture2D" path="res://{texture}" id="2_tex"]')

    sub = _shape_block(entity, "shape_1")
    load_steps = len(ext) + 1 + 1  # ext resources + one sub resource + 1

    if texture:
        visual = (
            f'[node name="Sprite" type="Sprite2D" parent="."]\n'
            f'texture = ExtResource("2_tex")\n'
        )
    else:
        # No art for this role: fall back to a polygon so the entity is never
        # invisible, which is the failure NO_VISUAL exists to catch.
        w, h = entity.size
        hw, hh = w / 2, h / 2
        visual = (
            f'[node name="Sprite" type="Polygon2D" parent="."]\n'
            f'color = Color(0.145, 0.827, 0.4, 1)\n'
            f'polygon = PackedVector2Array({-hw}, {-hh}, {hw}, {-hh}, {hw}, {hh}, {-hw}, {hh})\n'
        )

    return (
        f"[gd_scene load_steps={load_steps} format=3]\n\n"
        + "\n".join(ext) + "\n\n"
        + sub + "\n"
        + f'[node name="{entity.name}" type="{entity.body}"]\n'
          f'script = ExtResource("1_script")\n\n'
        + visual + "\n"
        + f'[node name="Shape" type="CollisionShape2D" parent="."]\n'
          f'shape = SubResource("shape_1")\n'
    )


def emit_main_scene(
    genre_id: str,
    level_script: str,
    sprites: Dict[str, str],
    window: tuple = (1152, 648),
    background: str = "#101014",
) -> str:
    """
    The world: a script, a background, the empty containers the level script
    fills, the player, and a HUD. Around a dozen nodes regardless of how large
    the level is, because the level is spawned at runtime.
    """
    entities = entities_for(genre_id)
    player = next((e for e in entities if e.name == "Player"), None)

    ext = [f'[ext_resource type="Script" path="res://{level_script}" id="1_main"]']
    if player:
        ext.append('[ext_resource type="PackedScene" path="res://scenes/Player.tscn" id="2_player"]')

    width, height = window
    r, g, b = _hex_to_rgb(background)

    nodes = [
        '[node name="Main" type="Node2D"]',
        'script = ExtResource("1_main")',
        "",
        '[node name="Background" type="ColorRect" parent="."]',
        "offset_right = %d.0" % width,
        "offset_bottom = %d.0" % height,
        f"color = Color({r:.3f}, {g:.3f}, {b:.3f}, 1)",
        "z_index = -100",
        "",
    ]
    for container in CONTAINERS:
        nodes += [f'[node name="{container}" type="Node2D" parent="."]', ""]

    if player:
        nodes += ['[node name="Player" parent="." instance=ExtResource("2_player")]', ""]

    nodes += [
        '[node name="HUD" type="CanvasLayer" parent="."]',
        "",
        '[node name="ScoreLabel" type="Label" parent="HUD"]',
        "offset_left = 24.0",
        "offset_top = 16.0",
        "offset_right = 400.0",
        "offset_bottom = 56.0",
        'text = "Score: 0"',
        "",
        '[node name="MessageLabel" type="Label" parent="HUD"]',
        "offset_left = 24.0",
        "offset_top = 56.0",
        "offset_right = 700.0",
        "offset_bottom = 96.0",
        'text = ""',
        "",
    ]

    load_steps = len(ext) + 1  # no sub resources here
    return (
        f"[gd_scene load_steps={load_steps} format=3]\n\n"
        + "\n".join(ext) + "\n\n"
        + "\n".join(nodes)
    )


def _hex_to_rgb(value: str) -> tuple:
    value = (value or "#101014").lstrip("#")
    if len(value) != 6:
        value = "101014"
    try:
        return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return (0.06, 0.08, 0.08)


def emit_all(
    project: Path,
    genre_id: str,
    sprites: Dict[str, str],
    level_script: str = "scripts/main.gd",
    window: tuple = (1152, 648),
    background: str = "#101014",
) -> Dict[str, List[str]]:
    """
    Write every scene. Returns the scene paths and the script paths the AI is
    now responsible for.
    """
    scenes_dir = project / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    entities = entities_for(genre_id)
    written: List[str] = []

    for entity in entities:
        path = scenes_dir / f"{entity.name}.tscn"
        path.write_text(emit_entity_scene(entity, sprites), encoding="utf-8")
        written.append(f"scenes/{entity.name}.tscn")

    (scenes_dir / "Main.tscn").write_text(
        emit_main_scene(genre_id, level_script, sprites, window, background),
        encoding="utf-8",
    )
    written.append("scenes/Main.tscn")

    scripts = [e.script for e in entities] + [level_script, "scripts/game_manager.gd"]
    logger.info(f"🏗️  Emitted {len(written)} scene(s) from templates (no AI)")
    return {"scenes": written, "scripts": sorted(set(scripts))}


def contract_block(genre_id: str, sprites: Dict[str, str]) -> str:
    """
    What the script-writing prompts must know about the scenes they are being
    written against. The scenes already exist by this point, so this describes
    reality rather than making a request.
    """
    entities = entities_for(genre_id)
    lines = [
        "THE SCENES ALREADY EXIST. You are writing scripts against them.",
        "",
        "scenes/Main.tscn  — the world. Its script is the level script.",
        "  Children you can rely on (look them up with $Name):",
    ]
    for container in CONTAINERS:
        lines.append(f"    ${container}        empty Node2D — spawn into this")
    lines += [
        "    $Player           already placed, instanced from Player.tscn",
        "    $HUD/ScoreLabel   Label",
        "    $HUD/MessageLabel Label",
        "",
        "Reusable scenes to instance at runtime:",
    ]
    for entity in entities:
        art = "sprite" if sprites.get(entity.sprite_role) else "polygon"
        lines.append(
            f"    res://scenes/{entity.name}.tscn  ({entity.body}, {art}, "
            f"script {entity.script}, group \"{entity.group}\")"
        )
    lines += [
        "",
        "Each of those scenes ALREADY has its sprite, its CollisionShape2D and",
        "its script attached. Do not recreate them — instance them:",
        "",
        "    const ENEMY := preload(\"res://scenes/Enemy.tscn\")",
        "    var e := ENEMY.instantiate()",
        "    e.position = Vector2(x, y)",
        "    $Enemies.add_child(e)",
        "",
        "Platforms have no scene: build them in code as StaticBody2D with a",
        "CollisionShape2D and a ColorRect or Sprite2D child, added to $Platforms.",
    ]
    return "\n".join(lines)
