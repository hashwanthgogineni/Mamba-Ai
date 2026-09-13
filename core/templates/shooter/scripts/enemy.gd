extends Area2D
## Enemy ship: drifts sideways, steps down at the edges, dies to one bullet.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 60.0
var _direction := 1.0


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("enemy_speed", speed))
	add_to_group("enemies")
	body_entered.connect(_on_body_entered)


func _physics_process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return

	position.x += _direction * speed * delta
	if position.x < 40.0 or position.x > float(LevelData.WORLD_WIDTH) - 40.0:
		_direction = -_direction
		position.y += 24.0

	# Reaching the player's line ends the run.
	if position.y > float(LevelData.WORLD_HEIGHT) - 80.0:
		GameManager.lose()


func _on_body_entered(body: Node2D) -> void:
	if body.is_in_group("player"):
		if body.has_method("die"):
			body.die()
		hit()


func hit() -> void:
	GameManager.collect()
	queue_free()
