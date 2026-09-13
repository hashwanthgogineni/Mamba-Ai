"""
Renders level_data.gd — the only file that differs between two games of the
same genre.

Everything else in a generated project is a fixed, hand-written template, so a
broken game cannot come from generated code. What varies is numbers, and those
are written here by Python with correct GDScript syntax by construction.

The AI never sees this file. It supplies a plan; this turns the plan into data.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DEFAULT_PALETTE = {
    "background": "#101014",
    "platform": "#3A3A45",
    "wall": "#2B4C8C",
    "player": "#25D366",
    "enemy": "#E8705F",
    "collectible": "#F2C94C",
}

# Per genre: the mechanics keys the template reads, with safe fallbacks. A plan
# that omits one, or supplies nonsense, still yields a playable game.
MECHANICS_DEFAULTS = {
    "platformer": {
        "speed": (300.0, 80.0, 700.0),
        "jump_velocity": (-450.0, -900.0, -200.0),
        "gravity": (980.0, 200.0, 3000.0),
        "max_fall_speed": (900.0, 200.0, 2000.0),
        "enemy_speed": (80.0, 10.0, 400.0),
    },
    "maze": {
        "tile_size": (32.0, 16.0, 64.0),
        "move_speed": (120.0, 40.0, 400.0),
        "enemy_speed": (95.0, 20.0, 400.0),
        "power_duration": (8.0, 1.0, 30.0),
    },
    "shooter": {
        "speed": (320.0, 80.0, 700.0),
        "fire_rate": (0.25, 0.05, 2.0),
        "bullet_speed": (600.0, 150.0, 1500.0),
        "enemy_speed": (60.0, 10.0, 400.0),
    },
    "runner": {
        "scroll_speed": (400.0, 100.0, 1200.0),
        "jump_velocity": (-500.0, -1000.0, -200.0),
        "gravity": (1200.0, 300.0, 3000.0),
        "speed_ramp": (1.05, 1.0, 1.5),
    },
    "topdown": {
        "speed": (220.0, 60.0, 600.0),
        "enemy_speed": (90.0, 20.0, 400.0),
        "attack_range": (48.0, 16.0, 200.0),
    },
    "puzzle": {
        "grid_width": (8.0, 4.0, 12.0),
        "grid_height": (10.0, 4.0, 14.0),
        "cell_size": (64.0, 32.0, 96.0),
        "colors": (5.0, 2.0, 8.0),
    },
}


def _clamp(value: Any, spec: tuple) -> float:
    default, low, high = spec
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return max(low, min(high, number))


def _gd_string(value: Any) -> str:
    return '"%s"' % str(value).replace("\\", "\\\\").replace('"', '\\"')


def _gd_pairs(entries: Any, width: int = 2) -> str:
    """Render a list of numeric tuples as GDScript array literals."""
    rows: List[str] = []
    for entry in entries or []:
        if not isinstance(entry, (list, tuple)) or len(entry) < width:
            continue
        numbers = []
        for item in entry:
            try:
                numbers.append(str(int(round(float(item)))))
            except (TypeError, ValueError):
                numbers.append("0")
        rows.append("\t[%s]," % ", ".join(numbers))
    return "\n".join(rows) if rows else ""


def _palette(plan: Dict) -> Dict[str, str]:
    palette = dict(DEFAULT_PALETTE)
    for key, value in (plan.get("palette") or {}).items():
        text = str(value)
        if text.startswith("#") and len(text) in (4, 7):
            palette[key] = text
    return palette


def _mechanics(plan: Dict, genre: str) -> Dict[str, float]:
    spec = MECHANICS_DEFAULTS.get(genre, MECHANICS_DEFAULTS["platformer"])
    supplied = plan.get("mechanics") or {}
    return {key: _clamp(supplied.get(key), rule) for key, rule in spec.items()}


def render(plan: Dict, genre: str) -> str:
    return {
        "maze": _render_maze,
        "shooter": _render_shooter,
        "runner": _render_runner,
        "topdown": _render_topdown,
        "puzzle": _render_puzzle,
    }.get(genre, _render_platformer)(plan)


def _header(plan: Dict, width: int, height: int, genre: str) -> str:
    palette = _palette(plan)
    mechanics = _mechanics(plan, genre)
    palette_rows = "\n".join(f'\t"{k}": "{v}",' for k, v in palette.items())
    mechanics_rows = "\n".join(f'\t"{k}": {v},' for k, v in mechanics.items())
    return f"""extends RefCounted
## GENERATED PER GAME — data only, never logic.
##
## Written by services/level_data.py from the plan. Every other script in this
## project is a fixed template, so the only thing that varies between two games
## is the numbers below.

const TITLE := {_gd_string(plan.get("title") or "Game")}
const WORLD_WIDTH := {width}
const WORLD_HEIGHT := {height}

const MECHANICS := {{
{mechanics_rows}
}}

const PALETTE := {{
{palette_rows}
}}
"""


def _render_platformer(plan: Dict) -> str:
    window = plan.get("window") or {}
    width = int(window.get("width") or 1152)
    height = int(window.get("height") or 648)
    level = plan.get("level") or {}

    spawn = level.get("spawn") or [80, height - 128]
    try:
        spawn_x, spawn_y = int(spawn[0]), int(spawn[1])
    except (TypeError, ValueError, IndexError):
        spawn_x, spawn_y = 80, height - 128

    platforms = _gd_pairs(level.get("platforms"), 4)
    if not platforms:
        # A level with no ground is unplayable; give it a floor.
        platforms = f"\t[0, {height - 48}, {width}, 48],"

    enemies = _gd_pairs(level.get("enemies"), 2)
    collectibles = _gd_pairs(level.get("collectibles"), 2)

    return _header(plan, width, height, "platformer") + f"""
const SPAWN := [{spawn_x}, {spawn_y}]

## [x, y, width, height]
const PLATFORMS := [
{platforms}
]

## [x, y] or [x, y, patrol_distance]
const ENEMIES := [
{enemies}
]

## [x, y]
const COLLECTIBLES := [
{collectibles}
]


static func color_of(key: String) -> Color:
\treturn Color(PALETTE.get(key, "#FFFFFF"))
"""


def _render_maze(plan: Dict) -> str:
    level = plan.get("level") or {}
    grid = [str(row) for row in (level.get("grid") or []) if str(row).strip()]

    # Every row must be the same length or the grid lookup goes out of step.
    if grid:
        widest = max(len(row) for row in grid)
        grid = [row.ljust(widest, "#") for row in grid]
    else:
        grid = ["#" * 20] + ["#" + "." * 18 + "#"] * 8 + ["#" * 20]
        grid[5] = "#" + "." * 8 + "P" + "." * 9 + "#"
        grid[3] = "#" + "." * 4 + "G" + "." * 13 + "#"

    mechanics = _mechanics(plan, "maze")
    tile = int(mechanics["tile_size"])
    width = len(grid[0]) * tile
    height = len(grid) * tile

    # The spawn is wherever 'P' sits; fall back to the first walkable cell.
    spawn_x = spawn_y = None
    for row_index, row in enumerate(grid):
        column = row.find("P")
        if column != -1:
            spawn_x = column * tile + tile // 2
            spawn_y = row_index * tile + tile // 2
            break
    if spawn_x is None:
        for row_index, row in enumerate(grid):
            for column, cell in enumerate(row):
                if cell != "#":
                    spawn_x = column * tile + tile // 2
                    spawn_y = row_index * tile + tile // 2
                    break
            if spawn_x is not None:
                break
    if spawn_x is None:
        spawn_x, spawn_y = tile, tile

    grid_rows = "\n".join(f"\t{_gd_string(row)}," for row in grid)

    return _header(plan, width, height, "maze") + f"""
## '#' wall, '.' pellet, 'o' power pellet, 'G' enemy start, 'P' player start.
## Every row is the same length.
const GRID := [
{grid_rows}
]

const SPAWN := [{spawn_x}, {spawn_y}]


static func color_of(key: String) -> Color:
\treturn Color(PALETTE.get(key, "#FFFFFF"))


## Which grid cell a world position falls in. Out of bounds counts as wall, so
## nothing can walk off the board.
static func cell_at(world: Vector2) -> String:
\tvar tile := float(MECHANICS.get("tile_size", 32))
\tvar col := int(floor(world.x / tile))
\tvar row := int(floor(world.y / tile))
\tif row < 0 or row >= GRID.size():
\t\treturn "#"
\tvar line: String = GRID[row]
\tif col < 0 or col >= line.length():
\t\treturn "#"
\treturn line[col]
"""


def write(project: Path, plan: Dict, genre: str) -> str:
    """Write scripts/level_data.gd. Returns the relative path."""
    target = project / "scripts" / "level_data.gd"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(plan, genre), encoding="utf-8")
    logger.info(f"📊 Wrote level_data.gd for '{genre}'")
    return "scripts/level_data.gd"


_COLOR_FN = """

static func color_of(key: String) -> Color:
\treturn Color(PALETTE.get(key, "#FFFFFF"))
"""


def _window(plan: Dict) -> tuple:
    window = plan.get("window") or {}
    return int(window.get("width") or 1152), int(window.get("height") or 648)


def _point(value: Any, fallback: tuple) -> tuple:
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError, IndexError):
        return fallback


def _render_shooter(plan: Dict) -> str:
    width, height = _window(plan)
    level = plan.get("level") or {}
    start = _point(level.get("player_start"), (width // 2, height - 60))

    waves: List[str] = []
    for wave in level.get("waves") or []:
        if not isinstance(wave, dict):
            continue
        waves.append(
            '\t{"count": %d, "rows": %d, "start_y": %d},'
            % (
                max(1, min(int(wave.get("count", 8) or 8), 40)),
                max(1, min(int(wave.get("rows", 1) or 1), 5)),
                max(40, min(int(wave.get("start_y", 80) or 80), height - 200)),
            )
        )
    if not waves:
        waves = ['\t{"count": 10, "rows": 2, "start_y": 80},']

    bounds = level.get("player_bounds") or [40, width - 40]
    low, high = _point(bounds, (40, width - 40))

    return _header(plan, width, height, "shooter") + f"""
const PLAYER_START := [{start[0]}, {start[1]}]
const PLAYER_BOUNDS := [{low}, {high}]

## Each wave: count, rows, start_y
const WAVES := [
{chr(10).join(waves)}
]
{_COLOR_FN}"""


def _render_runner(plan: Dict) -> str:
    width, height = _window(plan)
    level = plan.get("level") or {}
    ground = int(level.get("ground_y") or (height - 120))
    start = _point(level.get("player_start"), (200, ground))

    gap = level.get("spawn_interval") or [1.2, 2.4]
    try:
        low, high = float(gap[0]), float(gap[1])
    except (TypeError, ValueError, IndexError):
        low, high = 1.2, 2.4
    low = max(0.4, min(low, 4.0))
    high = max(low + 0.2, min(high, 6.0))

    return _header(plan, width, height, "runner") + f"""
const GROUND_Y := {ground}
const PLAYER_START := [{start[0]}, {start[1]}]
const SPAWN_INTERVAL := [{low}, {high}]
{_COLOR_FN}"""


def _render_topdown(plan: Dict) -> str:
    width, height = _window(plan)
    level = plan.get("level") or {}
    start = _point(level.get("player_start"), (width // 2, height // 2))

    walls = _gd_pairs(level.get("walls"), 4)
    if not walls:
        # Always enclose the room, or the player walks into nothing.
        walls = "\n".join([
            f"\t[0, 0, {width}, 32],",
            f"\t[0, {height - 32}, {width}, 32],",
            f"\t[0, 0, 32, {height}],",
            f"\t[{width - 32}, 0, 32, {height}],",
        ])

    enemies = _gd_pairs(level.get("enemies"), 2)
    pickups = _gd_pairs(level.get("pickups") or level.get("collectibles"), 2)

    return _header(plan, width, height, "topdown") + f"""
const PLAYER_START := [{start[0]}, {start[1]}]

## [x, y, width, height]
const WALLS := [
{walls}
]

## [x, y]
const ENEMIES := [
{enemies}
]

## [x, y]
const PICKUPS := [
{pickups}
]
{_COLOR_FN}"""


def _render_puzzle(plan: Dict) -> str:
    width, height = _window(plan)
    level = plan.get("level") or {}
    mechanics = _mechanics(plan, "puzzle")
    cols, rows = int(mechanics["grid_width"]), int(mechanics["grid_height"])
    cell = int(mechanics["cell_size"])
    origin = _point(
        level.get("origin"),
        (max(0, (width - cols * cell) // 2), max(0, (height - rows * cell) // 2)),
    )

    return _header(plan, width, height, "puzzle") + f"""
const ORIGIN := [{origin[0]}, {origin[1]}]
{_COLOR_FN}"""
