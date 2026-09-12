extends CharacterBody2D
## Grid-locked maze movement. No gravity, no jumping.
##
## Moves one tile at a time along corridors, queueing the next turn so a
## direction pressed slightly early still takes effect at the junction.
## Hand-written template — never generated.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 120.0
var tile: float = 32.0

var _dir := Vector2i.ZERO
var _queued := Vector2i.ZERO
var _target := Vector2.ZERO


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("move_speed", speed))
	tile = float(LevelData.MECHANICS.get("tile_size", tile))
	_target = global_position
	add_to_group("player")


func _physics_process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return

	var input := Vector2i.ZERO
	if Input.is_action_pressed("ui_left"):
		input = Vector2i(-1, 0)
	elif Input.is_action_pressed("ui_right"):
		input = Vector2i(1, 0)
	elif Input.is_action_pressed("ui_up"):
		input = Vector2i(0, -1)
	elif Input.is_action_pressed("ui_down"):
		input = Vector2i(0, 1)
	if input != Vector2i.ZERO:
		_queued = input

	# Only change direction when sitting on a tile centre.
	if global_position.distance_to(_target) < 1.0:
		global_position = _target
		if _queued != Vector2i.ZERO and _can_walk(_queued):
			_dir = _queued
			_queued = Vector2i.ZERO
		if _dir != Vector2i.ZERO and _can_walk(_dir):
			_target = global_position + Vector2(_dir) * tile
		else:
			_dir = Vector2i.ZERO

	if global_position != _target:
		global_position = global_position.move_toward(_target, speed * delta)


func _can_walk(direction: Vector2i) -> bool:
	var cell := LevelData.cell_at(global_position + Vector2(direction) * tile)
	return cell != "#"


func die() -> void:
	GameManager.lose_life()
	global_position = Vector2(
		float(LevelData.SPAWN[0]), float(LevelData.SPAWN[1])
	)
	_target = global_position
	_dir = Vector2i.ZERO
	_queued = Vector2i.ZERO
