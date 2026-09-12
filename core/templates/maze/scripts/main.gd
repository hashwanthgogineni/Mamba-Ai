extends Node2D
## Builds the maze from level_data.gd: one wall per '#', one pellet per '.'.
##
## Hand-written template — never generated.

const LevelData := preload("res://scripts/level_data.gd")

const ENEMY_SCENE := preload("res://scenes/Enemy.tscn")
const COLLECTIBLE_SCENE := preload("res://scenes/Collectible.tscn")

@onready var platforms: Node2D = $Platforms
@onready var enemies: Node2D = $Enemies
@onready var collectibles: Node2D = $Collectibles
@onready var player: CharacterBody2D = $Player
@onready var score_label: Label = $HUD/ScoreLabel
@onready var message_label: Label = $HUD/MessageLabel

var _pellet_count := 0


func _ready() -> void:
	_build_maze()
	_place_player()

	GameManager.reset(_pellet_count)
	GameManager.score_changed.connect(_refresh_hud)
	GameManager.lives_changed.connect(_refresh_hud)
	GameManager.game_won.connect(_on_won)
	GameManager.game_lost.connect(_on_lost)
	_refresh_hud(0)


func _process(_delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		if Input.is_action_just_pressed("ui_accept"):
			GameManager.restart()


func _build_maze() -> void:
	var tile := float(LevelData.MECHANICS.get("tile_size", 32))
	var wall_color: Color = LevelData.color_of("wall")

	for row in range(LevelData.GRID.size()):
		var line: String = LevelData.GRID[row]
		for col in range(line.length()):
			var cell := line[col]
			var pos := Vector2(col * tile + tile * 0.5, row * tile + tile * 0.5)

			match cell:
				"#":
					_add_wall(pos, tile, wall_color)
				".", "o":
					var item := COLLECTIBLE_SCENE.instantiate()
					item.position = pos
					collectibles.add_child(item)
					_pellet_count += 1
				"G":
					var enemy := ENEMY_SCENE.instantiate()
					enemy.position = pos
					enemies.add_child(enemy)


func _add_wall(pos: Vector2, tile: float, wall_color: Color) -> void:
	var body := StaticBody2D.new()
	body.position = pos
	body.add_to_group("platforms")

	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile, tile)
	shape.shape = rect
	body.add_child(shape)

	var visual := ColorRect.new()
	visual.size = Vector2(tile, tile)
	visual.position = Vector2(-tile * 0.5, -tile * 0.5)
	visual.color = wall_color
	visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(visual)

	platforms.add_child(body)


func _place_player() -> void:
	if player != null:
		player.global_position = Vector2(
			float(LevelData.SPAWN[0]), float(LevelData.SPAWN[1])
		)


func _refresh_hud(_value: int = 0) -> void:
	if score_label != null:
		score_label.text = "Score: %d    Lives: %d" % [GameManager.score, GameManager.lives]


func _on_won() -> void:
	if message_label != null:
		message_label.text = "All pellets eaten!  Press Space to play again."


func _on_lost() -> void:
	if message_label != null:
		message_label.text = "Caught!  Press Space to try again."
