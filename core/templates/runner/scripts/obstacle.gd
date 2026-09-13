extends Area2D
## Scrolls toward the player; contact costs a life.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 400.0


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("scroll_speed", speed))
	add_to_group("obstacles")
	body_entered.connect(_on_body_entered)


func _physics_process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return
	position.x -= speed * delta
	if position.x < -120.0:
		queue_free()


func _on_body_entered(body: Node2D) -> void:
	if body.is_in_group("player"):
		if body.has_method("die"):
			body.die()
		queue_free()
