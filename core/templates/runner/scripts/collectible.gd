extends Area2D
## Scrolling pickup.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 400.0
var _taken := false


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("scroll_speed", speed))
	add_to_group("collectibles")
	body_entered.connect(_on_body_entered)


func _physics_process(delta: float) -> void:
	position.x -= speed * delta
	if position.x < -120.0:
		queue_free()


func _on_body_entered(body: Node2D) -> void:
	if _taken or not body.is_in_group("player"):
		return
	_taken = true
	GameManager.add_score(10)
	queue_free()
