extends CharacterBody2D
## Player controller: run, jump, gravity, death and respawn.
##
## Hand-written template — never generated. Tuning values come from
## level_data.gd so a generated game can change the feel without changing code.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 300.0
var jump_velocity: float = -450.0
var gravity: float = 980.0
var max_fall_speed: float = 900.0

## Grace period after walking off a ledge during which a jump still works.
const COYOTE_TIME := 0.10
## A jump pressed slightly before landing is remembered rather than dropped.
const JUMP_BUFFER := 0.12

var _coyote := 0.0
var _buffer := 0.0
var _spawn := Vector2.ZERO


func _ready() -> void:
	var m: Dictionary = LevelData.MECHANICS
	speed = float(m.get("speed", speed))
	jump_velocity = float(m.get("jump_velocity", jump_velocity))
	gravity = float(m.get("gravity", gravity))
	max_fall_speed = float(m.get("max_fall_speed", max_fall_speed))
	_spawn = global_position
	add_to_group("player")


func _physics_process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return

	if is_on_floor():
		_coyote = COYOTE_TIME
	else:
		_coyote = max(_coyote - delta, 0.0)
		velocity.y = min(velocity.y + gravity * delta, max_fall_speed)

	if Input.is_action_just_pressed("ui_accept"):
		_buffer = JUMP_BUFFER
	else:
		_buffer = max(_buffer - delta, 0.0)

	if _buffer > 0.0 and _coyote > 0.0:
		velocity.y = jump_velocity
		_buffer = 0.0
		_coyote = 0.0

	var direction := Input.get_axis("ui_left", "ui_right")
	if direction != 0.0:
		velocity.x = direction * speed
		if has_node("Sprite"):
			var sprite := get_node("Sprite")
			if sprite is Sprite2D:
				(sprite as Sprite2D).flip_h = direction < 0.0
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed * 4.0 * delta)

	move_and_slide()

	# Falling out of the world costs a life, same as touching an enemy.
	if global_position.y > LevelData.WORLD_HEIGHT + 400.0:
		die()


func die() -> void:
	GameManager.lose_life()
	velocity = Vector2.ZERO
	global_position = _spawn
