extends Area2D
## One board tile. Click to clear it and score.

var colour_index := 0
var _cleared := false


func _ready() -> void:
	add_to_group("tiles")
	input_event.connect(_on_input_event)


func _on_input_event(_viewport: Node, event: InputEvent, _shape: int) -> void:
	if _cleared or GameManager.state != GameManager.State.PLAYING:
		return
	if event is InputEventMouseButton and event.pressed:
		clear_tile()


func clear_tile() -> void:
	if _cleared:
		return
	_cleared = true
	GameManager.collect()
	queue_free()
