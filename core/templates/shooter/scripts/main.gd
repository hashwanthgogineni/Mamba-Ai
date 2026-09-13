extends Node2D
## Spawns enemy waves from level_data.gd and wires the HUD.

const LevelData := preload("res://scripts/level_data.gd")
const ENEMY := preload("res://scenes/Enemy.tscn")

@onready var enemies: Node2D = $Enemies
@onready var player: CharacterBody2D = $Player
@onready var score_label: Label = $HUD/ScoreLabel
@onready var message_label: Label = $HUD/MessageLabel

var _total := 0


func _ready() -> void:
	_spawn_waves()
	if player != null:
		player.global_position = Vector2(
			float(LevelData.PLAYER_START[0]), float(LevelData.PLAYER_START[1])
		)

	GameManager.reset(_total)
	GameManager.score_changed.connect(_refresh_hud)
	GameManager.lives_changed.connect(_refresh_hud)
	GameManager.game_won.connect(_on_won)
	GameManager.game_lost.connect(_on_lost)
	_refresh_hud(0)


func _process(_delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		if Input.is_action_just_pressed("ui_accept"):
			GameManager.restart()


func _spawn_waves() -> void:
	for wave in LevelData.WAVES:
		var count := int(wave.get("count", 8))
		var rows := maxi(int(wave.get("rows", 1)), 1)
		var start_y := float(wave.get("start_y", 80))
		var per_row := maxi(count / rows, 1)
		var gap_x := float(LevelData.WORLD_WIDTH - 160) / float(maxi(per_row - 1, 1))

		for index in range(count):
			var row := index / per_row
			var column := index % per_row
			var enemy := ENEMY.instantiate()
			enemy.position = Vector2(80.0 + column * gap_x, start_y + row * 60.0)
			enemies.add_child(enemy)
			_total += 1


func _refresh_hud(_value: int = 0) -> void:
	if score_label != null:
		score_label.text = "Score: %d    Lives: %d" % [GameManager.score, GameManager.lives]


func _on_won() -> void:
	if message_label != null:
		message_label.text = "All clear!  Press Space to play again."


func _on_lost() -> void:
	if message_label != null:
		message_label.text = "Shot down.  Press Space to try again."
