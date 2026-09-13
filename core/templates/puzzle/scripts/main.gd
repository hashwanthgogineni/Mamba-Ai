extends Node2D
## Builds the puzzle board from level_data.gd.

const LevelData := preload("res://scripts/level_data.gd")
const TILE := preload("res://scenes/Tile.tscn")

@onready var tiles_root: Node2D = $Collectibles
@onready var score_label: Label = $HUD/ScoreLabel
@onready var message_label: Label = $HUD/MessageLabel

var _total := 0


func _ready() -> void:
	_build_board()
	GameManager.reset(_total)
	GameManager.score_changed.connect(_refresh_hud)
	GameManager.game_won.connect(_on_won)
	_refresh_hud(0)


func _process(_delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		if Input.is_action_just_pressed("ui_accept"):
			GameManager.restart()


func _build_board() -> void:
	var m: Dictionary = LevelData.MECHANICS
	var cols := int(m.get("grid_width", 8))
	var rows := int(m.get("grid_height", 10))
	var cell := float(m.get("cell_size", 64))
	var origin: Array = LevelData.ORIGIN

	for row in range(rows):
		for col in range(cols):
			var tile := TILE.instantiate()
			tile.position = Vector2(
				float(origin[0]) + col * cell + cell * 0.5,
				float(origin[1]) + row * cell + cell * 0.5
			)
			tile.colour_index = (row + col) % int(m.get("colors", 5))
			tiles_root.add_child(tile)
			_total += 1


func _refresh_hud(_value: int = 0) -> void:
	if score_label != null:
		score_label.text = "Score: %d" % GameManager.score


func _on_won() -> void:
	if message_label != null:
		message_label.text = "Board cleared!  Press Space to play again."
