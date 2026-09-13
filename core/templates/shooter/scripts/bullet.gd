extends Area2D
## Player projectile: travels up, kills one enemy, removes itself off-screen.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 600.0


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("bullet_speed", speed))
	add_to_group("bullets")
	area_entered.connect(_on_area_entered)


func _physics_process(delta: float) -> void:
	position.y -= speed * delta
	if position.y < -64.0:
		queue_free()


func _on_area_entered(area: Area2D) -> void:
	if area.is_in_group("enemies"):
		if area.has_method("hit"):
			area.hit()
		queue_free()
