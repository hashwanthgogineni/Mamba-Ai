extends CharacterBody2D
## Maze hunter. Walks corridors, turning at junctions, biased toward the player.
##
## Hand-written template — never generated.

const LevelData := preload("res://scripts/level_data.gd")

var speed: float = 100.0
var tile: float = 32.0

var _dir := Vector2i.RIGHT
var _target := Vector2.ZERO


func _ready() -> void:
	speed = float(LevelData.MECHANICS.get("enemy_speed", speed))
	tile = float(LevelData.MECHANICS.get("tile_size", tile))
	_target = global_position
	add_to_group("enemies")


func _physics_process(delta: float) -> void:
	if GameManager.state != GameManager.State.PLAYING:
		return

	if global_position.distance_to(_target) < 1.0:
		global_position = _target
		_choose_direction()
		_target = global_position + Vector2(_dir) * tile

	global_position = global_position.move_toward(_target, speed * delta)

	var player := get_tree().get_first_node_in_group("player")
	if player != null and global_position.distance_to(player.global_position) < tile * 0.7:
		if player.has_method("die"):
			player.die()


func _choose_direction() -> void:
	var options: Array[Vector2i] = []
	for candidate in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		if LevelData.cell_at(global_position + Vector2(candidate) * tile) != "#":
			options.append(candidate)

	if options.is_empty():
		_dir = Vector2i.ZERO
		return

	# Prefer not to reverse, so it patrols rather than jittering in place.
	var forward := options.filter(func(d): return d != -_dir)
	if not forward.is_empty():
		options = forward

	var player := get_tree().get_first_node_in_group("player")
	if player != null and randf() < 0.65:
		var best: Vector2i = options[0]
		var best_distance := INF
		for candidate in options:
			var probe := global_position + Vector2(candidate) * tile
			var distance := probe.distance_to(player.global_position)
			if distance < best_distance:
				best_distance = distance
				best = candidate
		_dir = best
	else:
		_dir = options[randi() % options.size()]
