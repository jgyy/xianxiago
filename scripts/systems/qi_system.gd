extends Node
## Autoload: the player's qi (internal energy) pool.
## Sprinting and the light-body (qinggong) glide/double-jump drain qi;
## it regenerates passively when not being spent. Combat/techniques will
## draw on this same pool later.

signal qi_changed(current: float, max_qi: float)
signal qi_depleted
signal qi_restored_full

@export var regen_rate: float = 12.0 ## qi per second while regenerating
@export var regen_delay: float = 1.0 ## seconds of no spending before regen resumes

var max_qi: float = 100.0
var current_qi: float = 100.0

var _regen_cooldown: float = 0.0

func _ready() -> void:
	max_qi = GameState.max_qi_for_realm()
	current_qi = max_qi
	GameState.realm_changed.connect(_on_realm_changed)

func _process(delta: float) -> void:
	if _regen_cooldown > 0.0:
		_regen_cooldown -= delta
		return
	if current_qi < max_qi:
		_set_qi(minf(max_qi, current_qi + regen_rate * delta))

## Attempts to spend `amount` qi. Returns false (and spends nothing) if
## there isn't enough left, so callers can bail out of a qi-costing action.
func try_spend(amount: float) -> bool:
	if amount <= 0.0:
		return true
	if current_qi < amount:
		return false
	_set_qi(current_qi - amount)
	_regen_cooldown = regen_delay
	return true

## Continuous drain for held actions (e.g. gliding). Returns the actual
## amount drained, which may be less than requested if qi ran out.
func drain(amount_per_second: float, delta: float) -> float:
	var requested := amount_per_second * delta
	var actual := minf(requested, current_qi)
	if actual > 0.0:
		_set_qi(current_qi - actual)
		_regen_cooldown = regen_delay
	return actual

func has_qi(amount: float) -> bool:
	return current_qi >= amount

func ratio() -> float:
	if max_qi <= 0.0:
		return 0.0
	return current_qi / max_qi

func _set_qi(value: float) -> void:
	var clamped := clampf(value, 0.0, max_qi)
	var was_empty := current_qi <= 0.0
	var was_full := current_qi >= max_qi
	current_qi = clamped
	qi_changed.emit(current_qi, max_qi)
	if current_qi <= 0.0 and not was_empty:
		qi_depleted.emit()
	if current_qi >= max_qi and not was_full:
		qi_restored_full.emit()

func _on_realm_changed(_new_realm) -> void:
	var old_ratio := ratio()
	max_qi = GameState.max_qi_for_realm()
	current_qi = max_qi * old_ratio
	qi_changed.emit(current_qi, max_qi)
