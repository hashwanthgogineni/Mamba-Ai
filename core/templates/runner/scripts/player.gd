extends CharacterBody2D
## Endless runner: the world scrolls, the player only jumps.

const LevelData := preload("res://scripts/level_data.gd")

var jump_velocity: float = -500.0
var gravity: float = 1200.0
var _ground_y: float = 0.0


func _ready() -> void:
	var m: Dictionary = LevelData.MECHANICS
	jump_velocity = float(m.get("jump_velocity", jump_velocity))
	gravity = float(m.get("gravity", gravity))
	_ground_y = float(LevelData.GROUND_Y)
	add_to_group("player")


func _physics_process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return

	velocity.y += gravity * delta

	var grounded := global_position.y >= _ground_y - 1.0
	if grounded:
		global_position.y = _ground_y
		velocity.y = minf(velocity.y, 0.0)
		if Input.is_action_just_pressed("ui_accept") or Input.is_action_pressed("ui_up"):
			velocity.y = jump_velocity

	velocity.x = 0.0
	move_and_slide()


func die() -> void:
	GameManager.lose_life()
