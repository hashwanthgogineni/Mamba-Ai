extends Area2D
## A pickup. Scores once, then removes itself.
##
## Hand-written template — never generated.

var _taken := false


func _ready() -> void:
	add_to_group("collectibles")
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node2D) -> void:
	if _taken or not body.is_in_group("player"):
		return
	_taken = true
	GameManager.collect()
	queue_free()
