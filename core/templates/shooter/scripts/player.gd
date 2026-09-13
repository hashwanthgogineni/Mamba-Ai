extends CharacterBody2D
## Ship: moves left/right within bounds, fires upward on a cooldown.

const LevelData := preload("res://scripts/level_data.gd")
const BULLET := preload("res://scenes/Bullet.tscn")

var speed: float = 320.0
var fire_rate: float = 0.25
var _cooldown := 0.0


func _ready() -> void:
	var m: Dictionary = LevelData.MECHANICS
	speed = float(m.get("speed", speed))
	fire_rate = float(m.get("fire_rate", fire_rate))
	add_to_group("player")


func _physics_process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return

	# No gravity: this is a top-down shooter.
	var direction := Input.get_axis("ui_left", "ui_right")
	velocity = Vector2(direction * speed, 0.0)
	move_and_slide()

	var bounds: Array = LevelData.PLAYER_BOUNDS
	global_position.x = clampf(global_position.x, float(bounds[0]), float(bounds[1]))

	_cooldown = maxf(_cooldown - delta, 0.0)
	if Input.is_action_pressed("ui_accept") and _cooldown <= 0.0:
		_shoot()
		_cooldown = fire_rate


func _shoot() -> void:
	var bullet := BULLET.instantiate()
	bullet.global_position = global_position + Vector2(0, -32)
	get_tree().current_scene.get_node("Projectiles").add_child(bullet)


func die() -> void:
	GameManager.lose_life()
