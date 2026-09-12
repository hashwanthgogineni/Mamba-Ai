extends RefCounted
## GENERATED PER GAME — data only, never logic.
##
## The builder rewrites this file from the plan's level data. Every other
## script in the project is a fixed template, so a broken game cannot come
## from generated code: the only thing that varies is numbers.

const TITLE := "Platformer"
const WORLD_WIDTH := 1152
const WORLD_HEIGHT := 648

const MECHANICS := {
	"speed": 300.0,
	"jump_velocity": -450.0,
	"gravity": 980.0,
	"max_fall_speed": 900.0,
	"enemy_speed": 80.0,
}

const PALETTE := {
	"background": "#101014",
	"platform": "#3A3A45",
	"player": "#25D366",
	"enemy": "#E8705F",
	"collectible": "#F2C94C",
}

const SPAWN := [80, 520]

## [x, y, width, height]
const PLATFORMS := [
	[0, 600, 1152, 48],
	[180, 500, 160, 24],
	[420, 430, 180, 24],
	[700, 470, 150, 24],
	[900, 380, 200, 24],
]

## [x, y] or [x, y, patrol_distance]
const ENEMIES := [
	[240, 470, 60],
	[470, 400, 70],
]

## [x, y]
const COLLECTIBLES := [
	[200, 450],
	[460, 380],
	[740, 420],
	[950, 330],
]


static func color_of(key: String) -> Color:
	return Color(PALETTE.get(key, "#FFFFFF"))
