extends Node2D
## Builds the level from level_data.gd and wires the HUD.
##
## Hand-written template — never generated. Everything that varies per game
## lives in level_data.gd, which contains data and no logic at all.

const LevelData := preload("res://scripts/level_data.gd")

const ENEMY_SCENE := preload("res://scenes/Enemy.tscn")
const COLLECTIBLE_SCENE := preload("res://scenes/Collectible.tscn")

@onready var platforms: Node2D = $Platforms
@onready var enemies: Node2D = $Enemies
@onready var collectibles: Node2D = $Collectibles
@onready var player: CharacterBody2D = $Player
@onready var score_label: Label = $HUD/ScoreLabel
@onready var message_label: Label = $HUD/MessageLabel


func _ready() -> void:
	_build_platforms()
	_build_enemies()
	_build_collectibles()
	_place_player()

	GameManager.reset(LevelData.COLLECTIBLES.size())
	GameManager.score_changed.connect(_on_score_changed)
	GameManager.lives_changed.connect(_on_lives_changed)
	GameManager.game_won.connect(_on_won)
	GameManager.game_lost.connect(_on_lost)

	_refresh_hud()


func _process(_delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		if Input.is_action_just_pressed("ui_accept"):
			GameManager.restart()


func _build_platforms() -> void:
	for entry in LevelData.PLATFORMS:
		var x := float(entry[0])
		var y := float(entry[1])
		var w := float(entry[2])
		var h := float(entry[3])

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
		visual.color = LevelData.color_of("platform")
		visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
		body.add_child(visual)

		platforms.add_child(body)


func _build_enemies() -> void:
	for entry in LevelData.ENEMIES:
		var enemy := ENEMY_SCENE.instantiate()
		enemy.position = Vector2(float(entry[0]), float(entry[1]))
		if entry.size() > 2:
			enemy.patrol_distance = float(entry[2])
		enemies.add_child(enemy)


func _build_collectibles() -> void:
	for entry in LevelData.COLLECTIBLES:
		var item := COLLECTIBLE_SCENE.instantiate()
		item.position = Vector2(float(entry[0]), float(entry[1]))
		collectibles.add_child(item)


func _place_player() -> void:
	if player == null:
		return
	player.global_position = Vector2(
		float(LevelData.SPAWN[0]), float(LevelData.SPAWN[1])
	)


func _on_score_changed(_score: int) -> void:
	_refresh_hud()


func _on_lives_changed(_lives: int) -> void:
	_refresh_hud()


func _refresh_hud() -> void:
	if score_label != null:
		score_label.text = "Score: %d    Lives: %d" % [GameManager.score, GameManager.lives]


func _on_won() -> void:
	if message_label != null:
		message_label.text = "You win!  Press Space to play again."


func _on_lost() -> void:
	if message_label != null:
		message_label.text = "Game over.  Press Space to try again."
