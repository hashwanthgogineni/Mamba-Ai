extends Node2D
## Runner: ground, then obstacles and pickups spawned on a timer forever.

const LevelData := preload("res://scripts/level_data.gd")
const OBSTACLE := preload("res://scenes/Obstacle.tscn")
const COLLECTIBLE := preload("res://scenes/Collectible.tscn")

@onready var platforms: Node2D = $Platforms
@onready var obstacles: Node2D = $Enemies
@onready var collectibles: Node2D = $Collectibles
@onready var player: CharacterBody2D = $Player
@onready var score_label: Label = $HUD/ScoreLabel
@onready var message_label: Label = $HUD/MessageLabel

var _next_spawn := 1.0
var _distance := 0.0


func _ready() -> void:
	_build_ground()
	if player != null:
		player.global_position = Vector2(
			float(LevelData.PLAYER_START[0]), float(LevelData.PLAYER_START[1])
		)

	# Endless: there is nothing to collect them all of, so no win target.
	GameManager.reset(0)
	GameManager.score_changed.connect(_refresh_hud)
	GameManager.lives_changed.connect(_refresh_hud)
	GameManager.game_lost.connect(_on_lost)
	_refresh_hud(0)


func _process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		if Input.is_action_just_pressed("ui_accept"):
			GameManager.restart()
		return

	_distance += delta
	_next_spawn -= delta
	if _next_spawn <= 0.0:
		_spawn()
		var gap: Array = LevelData.SPAWN_INTERVAL
		_next_spawn = randf_range(float(gap[0]), float(gap[1]))


func _build_ground() -> void:
	var ground_y := float(LevelData.GROUND_Y) + 32.0
	var body := StaticBody2D.new()
	body.position = Vector2(float(LevelData.WORLD_WIDTH) * 0.5, ground_y + 24.0)
	body.add_to_group("platforms")

	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(float(LevelData.WORLD_WIDTH) * 3.0, 48.0)
	shape.shape = rect
	body.add_child(shape)

	var visual := ColorRect.new()
	visual.size = Vector2(float(LevelData.WORLD_WIDTH) * 3.0, 48.0)
	visual.position = Vector2(-float(LevelData.WORLD_WIDTH) * 1.5, -24.0)
	visual.color = LevelData.color_of("platform")
	visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(visual)

	platforms.add_child(body)


func _spawn() -> void:
	var x := float(LevelData.WORLD_WIDTH) + 80.0
	if randf() < 0.65:
		var obstacle := OBSTACLE.instantiate()
		obstacle.position = Vector2(x, float(LevelData.GROUND_Y))
		obstacles.add_child(obstacle)
	else:
		var item := COLLECTIBLE.instantiate()
		item.position = Vector2(x, float(LevelData.GROUND_Y) - 120.0)
		collectibles.add_child(item)


func _refresh_hud(_value: int = 0) -> void:
	if score_label != null:
		score_label.text = "Score: %d    Lives: %d    %dm" % [
			GameManager.score, GameManager.lives, int(_distance * 10.0)
		]


func _on_lost() -> void:
	if message_label != null:
		message_label.text = "Crashed!  Press Space to run again."
