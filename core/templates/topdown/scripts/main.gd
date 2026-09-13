extends Node2D
## Builds a walled room with enemies and pickups from level_data.gd.

const LevelData := preload("res://scripts/level_data.gd")
const ENEMY := preload("res://scenes/Enemy.tscn")
const COLLECTIBLE := preload("res://scenes/Collectible.tscn")

@onready var walls: Node2D = $Platforms
@onready var enemies: Node2D = $Enemies
@onready var collectibles: Node2D = $Collectibles
@onready var player: CharacterBody2D = $Player
@onready var score_label: Label = $HUD/ScoreLabel
@onready var message_label: Label = $HUD/MessageLabel


func _ready() -> void:
	for entry in LevelData.WALLS:
		_add_wall(float(entry[0]), float(entry[1]), float(entry[2]), float(entry[3]))

	for entry in LevelData.ENEMIES:
		var enemy := ENEMY.instantiate()
		enemy.position = Vector2(float(entry[0]), float(entry[1]))
		enemies.add_child(enemy)

	for entry in LevelData.PICKUPS:
		var item := COLLECTIBLE.instantiate()
		item.position = Vector2(float(entry[0]), float(entry[1]))
		collectibles.add_child(item)

	if player != null:
		player.global_position = Vector2(
			float(LevelData.PLAYER_START[0]), float(LevelData.PLAYER_START[1])
		)

	GameManager.reset(LevelData.PICKUPS.size())
	GameManager.score_changed.connect(_refresh_hud)
	GameManager.lives_changed.connect(_refresh_hud)
	GameManager.game_won.connect(_on_won)
	GameManager.game_lost.connect(_on_lost)
	_refresh_hud(0)


func _process(_delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		if Input.is_action_just_pressed("ui_accept"):
			GameManager.restart()


func _add_wall(x: float, y: float, w: float, h: float) -> void:
	var body := StaticBody2D.new()
	body.position = Vector2(x + w * 0.5, y + h * 0.5)
	body.add_to_group("platforms")

	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(w, h)
	shape.shape = rect
	body.add_child(shape)

	var visual := ColorRect.new()
	visual.size = Vector2(w, h)
	visual.position = Vector2(-w * 0.5, -h * 0.5)
	visual.color = LevelData.color_of("wall")
	visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(visual)

	walls.add_child(body)


func _refresh_hud(_value: int = 0) -> void:
	if score_label != null:
		score_label.text = "Score: %d    Lives: %d" % [GameManager.score, GameManager.lives]


func _on_won() -> void:
	if message_label != null:
		message_label.text = "Room cleared!  Press Space to play again."


func _on_lost() -> void:
	if message_label != null:
		message_label.text = "You fell.  Press Space to try again."
