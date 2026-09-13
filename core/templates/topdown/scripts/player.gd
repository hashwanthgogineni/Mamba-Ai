extends CharacterBody2D
## Top-down: 8-directional movement, no gravity.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 220.0


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("speed", speed))
	add_to_group("player")


func _physics_process(_delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return
	var direction := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	velocity = direction * speed
	move_and_slide()


func die() -> void:
	GameManager.lose_life()
	global_position = Vector2(
		float(LevelData.PLAYER_START[0]), float(LevelData.PLAYER_START[1])
	)
