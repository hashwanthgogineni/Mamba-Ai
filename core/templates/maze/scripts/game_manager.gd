extends Node
## Autoload singleton. Owns score, lives and win/lose state for the whole game.
##
## Hand-written template — never generated. Only level_data.gd changes per game.

signal score_changed(score: int)
signal lives_changed(lives: int)
signal game_won()
signal game_lost()

enum State { PLAYING, WON, LOST }

var score: int = 0
var lives: int = 3
var state: int = State.PLAYING

var _total_collectibles: int = 0
var _collected: int = 0


func reset(total_collectibles: int = 0) -> void:
	score = 0
	lives = 3
	state = State.PLAYING
	_collected = 0
	_total_collectibles = total_collectibles
	score_changed.emit(score)
	lives_changed.emit(lives)


func add_score(amount: int = 10) -> void:
	if state != State.PLAYING:
		return
	score += amount
	score_changed.emit(score)


func collect() -> void:
	if state != State.PLAYING:
		return
	_collected += 1
	add_score(10)
	if _total_collectibles > 0 and _collected >= _total_collectibles:
		win()


func lose_life() -> void:
	if state != State.PLAYING:
		return
	lives -= 1
	lives_changed.emit(lives)
	if lives <= 0:
		lose()


func win() -> void:
	if state != State.PLAYING:
		return
	state = State.WON
	game_won.emit()


func lose() -> void:
	if state != State.PLAYING:
		return
	state = State.LOST
	game_lost.emit()


func restart() -> void:
	reset(_total_collectibles)
	get_tree().reload_current_scene()
