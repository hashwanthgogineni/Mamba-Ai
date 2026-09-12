"""
Genre catalogue.

Each genre carries its own level/mechanics schema. That matters more than it
looks: a single platformer-shaped schema (platforms/gravity/jump) forces every
game through the wrong mould — ask it for Pac-Man and you get disconnected
blocks floating in space, because "maze corridors" has nowhere to live.

Each entry also declares what sprites the genre needs, so the asset stage knows
what to fetch without a second AI call.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Genre:
    id: str
    label: str
    example: str
    # Short description of how the game plays, fed to the planner.
    feel: str
    # The genre-specific part of the plan JSON schema.
    level_schema: str
    mechanics_schema: str
    # Rules the planner must respect for this genre.
    rules: List[str] = field(default_factory=list)
    # Sprite roles the asset stage should source.
    sprites: List[str] = field(default_factory=list)


GENRES: Dict[str, Genre] = {
    "maze": Genre(
        id="maze",
        label="Maze chase",
        example="Pac-Man, Bomberman",
        feel="Grid-locked movement through connected corridors, collecting "
             "pellets while enemies hunt you. No gravity, no jumping.",
        mechanics_schema='''"mechanics": {
    "tile_size": 32,
    "move_speed": 120.0,
    "enemy_speed": 100.0,
    "power_duration": 8.0
  }''',
        level_schema='''"level": {
    "grid": [
      "############################",
      "#............##............#",
      "#.####.#####.##.#####.####.#",
      "#o####.#####.##.#####.####o#",
      "#..........................#",
      "#.####.##.########.##.####.#",
      "#......##....##....##......#",
      "######.#####.##.#####.######",
      "#####..##..........##..#####",
      "#####.##.###G##G###.##.#####",
      "#........#G......G#........#",
      "#####.##.##########.##.#####",
      "#####.##..........G##..#####",
      "######.##.########.##.######",
      "#............##............#",
      "#.####.#####.##.#####.####.#",
      "#o..##.......P........##..o#",
      "###.##.##.########.##.##.###",
      "#......##....##....##......#",
      "#.##########.##.##########.#",
      "#..........................#",
      "############################"
    ],
    "legend": {"#": "wall", ".": "pellet", "o": "power pellet", " ": "empty",
               "P": "player start", "G": "enemy start"},
    "tile_size": 32
  }''',
        rules=[
            "The grid is the level. Every row string MUST be the same length.",
            "Corridors must be CONNECTED — a player must be able to walk from "
            "the player start to every pellet. Do not scatter isolated blocks.",
            "Walls form the maze structure; empty cells form walkable corridors "
            "exactly one tile wide.",
            "Include exactly one 'P' and at least two 'G' cells.",
            "Movement is 4-directional and aligned to the grid. There is NO "
            "gravity and NO jumping.",
            "Build the scene by iterating the grid: one wall node per '#', one "
            "pellet node per '.'.",
        ],
        sprites=["player", "enemy", "pellet", "power_pellet", "wall_tile"],
    ),

    "platformer": Genre(
        id="platformer",
        label="Platformer",
        example="Super Mario, Celeste",
        feel="Run and jump across platforms, avoiding enemies and reaching a goal.",
        mechanics_schema='''"mechanics": {
    "speed": 300.0,
    "jump_velocity": -450.0,
    "gravity": 980.0,
    "max_fall_speed": 900.0,
    "enemy_speed": 80.0
  }''',
        level_schema='''"level": {
    "spawn": [80, 520],
    "platforms": [[0, 600, 1152, 48], [180, 500, 160, 24], [420, 430, 180, 24],
                  [700, 470, 150, 24], [900, 380, 200, 24], [300, 300, 160, 24],
                  [600, 240, 180, 24], [860, 180, 160, 24], [120, 180, 140, 24],
                  [480, 120, 200, 24]],
    "enemies": [[220, 470], [470, 400], [740, 440], [950, 350], [340, 270], [650, 210]],
    "collectibles": [[200, 450], [260, 450], [460, 380], [520, 380], [740, 420],
                     [800, 420], [940, 330], [1000, 330], [340, 250], [400, 250],
                     [640, 190], [700, 190], [900, 130], [140, 130], [520, 70], [580, 70]],
    "goal": [1080, 90]
  }''',
        rules=[
            "Platforms are [x, y, width, height]; positions are [x, y].",
            "Every platform must be reachable: no gap wider than the jump arc "
            "(roughly 250px horizontally, 150px vertically).",
            "The player spawn must sit ABOVE a platform, never inside one.",
            "Enemies stand on platforms, never floating in mid-air.",
        ],
        sprites=["player", "enemy", "platform_tile", "coin", "background"],
    ),

    "shooter": Genre(
        id="shooter",
        label="Shooter",
        example="Space Invaders, Galaga",
        feel="Move and shoot at waves of incoming enemies. No gravity.",
        mechanics_schema='''"mechanics": {
    "speed": 320.0,
    "fire_rate": 0.25,
    "bullet_speed": 600.0,
    "enemy_speed": 60.0,
    "enemy_hp": 1
  }''',
        level_schema='''"level": {
    "player_start": [576, 600],
    "waves": [
      {"count": 10, "rows": 2, "enemy_type": "basic", "spacing": [90, 60], "start_y": 70},
      {"count": 10, "rows": 2, "enemy_type": "fast", "spacing": [90, 60], "start_y": 200},
      {"count": 6, "rows": 1, "enemy_type": "tank", "spacing": [140, 60], "start_y": 320}
    ],
    "player_bounds": [40, 1112]
  }''',
        rules=[
            "There is NO gravity. The player moves only within player_bounds.",
            "Enemies spawn in rows and advance toward the player.",
            "Bullets are spawned at runtime from a PackedScene, not placed in "
            "the level.",
        ],
        sprites=["player", "enemy", "bullet", "explosion", "background"],
    ),

    "runner": Genre(
        id="runner",
        label="Endless runner",
        example="Subway Surfers, Temple Run",
        feel="Automatic forward movement; dodge and jump obstacles. Score is distance.",
        mechanics_schema='''"mechanics": {
    "scroll_speed": 400.0,
    "jump_velocity": -500.0,
    "gravity": 1200.0,
    "speed_ramp": 1.05,
    "lane_count": 3
  }''',
        level_schema='''"level": {
    "ground_y": 600,
    "player_start": [200, 500],
    "obstacle_types": ["low", "high", "gap"],
    "spawn_interval": [1.2, 2.4],
    "lane_x": [400, 576, 752]
  }''',
        rules=[
            "Obstacles are spawned at runtime, never placed statically.",
            "The player never moves forward; the world scrolls toward them.",
            "Every obstacle must be avoidable by jumping or switching lanes.",
        ],
        sprites=["player", "obstacle", "ground_tile", "coin", "background"],
    ),

    "topdown": Genre(
        id="topdown",
        label="Top-down adventure",
        example="Zelda, Hotline Miami",
        feel="Explore a room from above with 8-directional movement. No gravity.",
        mechanics_schema='''"mechanics": {
    "speed": 220.0,
    "enemy_speed": 90.0,
    "attack_range": 48.0,
    "player_hp": 3
  }''',
        level_schema='''"level": {
    "player_start": [576, 324],
    "walls": [[0, 0, 1152, 32], [0, 616, 1152, 32], [0, 0, 32, 648], [1120, 0, 32, 648],
              [300, 140, 32, 220], [560, 300, 260, 32], [820, 120, 32, 200]],
    "enemies": [[300, 200], [800, 400], [500, 150], [900, 250], [420, 480], [700, 520]],
    "pickups": [[400, 300], [250, 420], [860, 180], [620, 220], [1020, 480], [180, 200]],
    "exit": [1100, 324]
  }''',
        rules=[
            "There is NO gravity. Movement is 8-directional.",
            "Walls must enclose the play area so the player cannot leave it.",
            "Enemies must have a clear path to the player.",
        ],
        sprites=["player", "enemy", "wall_tile", "pickup", "floor_tile"],
    ),

    "puzzle": Genre(
        id="puzzle",
        label="Puzzle",
        example="Tetris, Match-3",
        feel="Grid-based logic play. Pieces fall or swap; matches clear.",
        mechanics_schema='''"mechanics": {
    "grid_width": 8,
    "grid_height": 10,
    "cell_size": 64,
    "colors": 5,
    "match_length": 3
  }''',
        level_schema='''"level": {
    "origin": [320, 60],
    "initial_fill": "random",
    "moves_limit": 0,
    "target_score": 1000
  }''',
        rules=[
            "The board is generated at runtime from grid_width x grid_height.",
            "There is NO gravity in the physics sense; pieces move on the grid.",
            "Do not place individual cells in the scene; build the board in code.",
        ],
        sprites=["tile_a", "tile_b", "tile_c", "tile_d", "background"],
    ),
}

DEFAULT_GENRE = "platformer"


def get(genre_id: Optional[str]) -> Genre:
    return GENRES.get((genre_id or "").lower().strip(), GENRES[DEFAULT_GENRE])


def options() -> List[Dict[str, str]]:
    """The catalogue as the UI needs it."""
    return [
        {"id": g.id, "label": g.label, "example": g.example, "feel": g.feel}
        for g in GENRES.values()
    ]


def plan_schema(genre: Genre) -> str:
    """Assemble the full plan schema for one genre."""
    return f'''{{
  "title": "short game title",
  "description": "one sentence",
  "genre": "{genre.id}",
  "window": {{"width": 1152, "height": 648}},
  "main_scene": "scenes/Main.tscn",
  "palette": {{"background": "#101014", "player": "#25D366", "enemy": "#E8705F",
              "wall": "#3A3A45", "collectible": "#F2C94C"}},
  {genre.mechanics_schema},
  {genre.level_schema},
  "autoloads": {{"GameManager": "scripts/game_manager.gd"}},
  "scripts": [
    {{"path": "scripts/game_manager.gd", "extends": "Node",
     "purpose": "score, win/lose state, restart"}},
    {{"path": "scripts/player.gd", "extends": "CharacterBody2D",
     "purpose": "player control"}}
  ],
  "scenes": [
    {{"path": "scenes/Main.tscn", "root_type": "Node2D",
     "purpose": "the level",
     "nodes": ["Player", "Platforms", "Enemies", "Collectibles", "HUD"]}}
  ]
}}'''


CODE_LEVEL_RULE = (
    "- You do NOT write scene files. Every .tscn already exists, emitted from a "
    "template. Declare the level data as constants in the level script and SPAWN "
    "it in _ready() into the containers those scenes provide."
)

DENSITY_RULE = (
    "- Fill the play area. The example level above is the MINIMUM density, not a "
    "target: match it or exceed it. A level with a handful of objects reads as a "
    "broken demo, not a game."
)


def rules_block(genre: Genre) -> str:
    lines = "\n".join(f"- {r}" for r in genre.rules) + "\n" + DENSITY_RULE + "\n" + CODE_LEVEL_RULE
    return f"""GENRE: {genre.label} ({genre.example})
HOW IT PLAYS: {genre.feel}

GENRE RULES — these override any general instinct:
{lines}"""
