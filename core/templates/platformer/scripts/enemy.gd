extends CharacterBody2D
## Patrols a fixed horizontal span and costs the player a life on contact.
##
## Hand-written template — never generated.

const LevelData := preload("res://scripts/level_data.gd")

@export var patrol_distance: float = 120.0

var speed: float = 80.0
var _origin_x: float = 0.0
var _direction: float = 1.0


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("enemy_speed", speed))
	_origin_x = global_position.x
	add_to_group("enemies")


func _physics_process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return

	# Gravity keeps the enemy on its platform rather than drifting in the air.
	if not is_on_floor():
		velocity.y = min(velocity.y + 980.0 * delta, 900.0)
	else:
		velocity.y = 0.0

	if absf(global_position.x - _origin_x) >= patrol_distance:
		_direction = -_direction
		# Nudge back inside the span so it cannot get stuck at the edge.
		global_position.x = _origin_x + signf(global_position.x - _origin_x) * (patrol_distance - 1.0)

	velocity.x = _direction * speed
	move_and_slide()

	if has_node("Sprite"):
		var sprite := get_node("Sprite")
		if sprite is Sprite2D:
			(sprite as Sprite2D).flip_h = _direction < 0.0

	for i in get_slide_collision_count():
		var collider = get_slide_collision(i).get_collider()
		if collider != null and collider.is_in_group("player"):
			if collider.has_method("die"):
				collider.die()
