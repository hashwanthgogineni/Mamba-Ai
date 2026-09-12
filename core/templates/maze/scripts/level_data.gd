extends RefCounted
## GENERATED PER GAME — data only, never logic.

const TITLE := "Maze Chase"
const WORLD_WIDTH := 896
const WORLD_HEIGHT := 704

const MECHANICS := {
	"tile_size": 32,
	"move_speed": 120.0,
	"enemy_speed": 95.0,
	"power_duration": 8.0,
}

const PALETTE := {
	"background": "#101014",
	"wall": "#2B4C8C",
	"player": "#F2C94C",
	"enemy": "#E8705F",
	"collectible": "#F5E6C8",
}

## '#' wall, '.' pellet, 'o' power pellet, 'G' enemy start, 'P' player start,
## ' ' empty. Every row must be the same length.
const GRID := [
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
	"######.##..........##.######",
	"#............##............#",
	"#.####.#####.##.#####.####.#",
	"#o..##.......P........##..o#",
	"###.##.##.########.##.##.###",
	"#......##....##....##......#",
	"#.##########.##.##########.#",
	"#..........................#",
	"############################",
]

const SPAWN := [432, 496]


static func color_of(key: String) -> Color:
	return Color(PALETTE.get(key, "#FFFFFF"))


## Which grid cell a world position falls in. Out of bounds counts as wall so
## nothing can walk off the board.
static func cell_at(world: Vector2) -> String:
	var tile := float(MECHANICS.get("tile_size", 32))
	var col := int(floor(world.x / tile))
	var row := int(floor(world.y / tile))
	if row < 0 or row >= GRID.size():
		return "#"
	var line: String = GRID[row]
	if col < 0 or col >= line.length():
		return "#"
	return line[col]
