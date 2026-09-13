extends CharacterBody2D
## Walks toward the player once close enough, otherwise holds position.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 90.0
const DETECTION := 340.0


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("enemy_speed", speed))
	add_to_group("enemies")


func _physics_process(_delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return

	var player := get_tree().get_first_node_in_group("player")
	if player == null:
		return

	var to_player: Vector2 = player.global_position - global_position
	if to_player.length() < DETECTION:
		velocity = to_player.normalized() * speed
	else:
		velocity = Vector2.ZERO
	move_and_slide()

	if to_player.length() < 34.0 and player.has_method("die"):
		player.die()
