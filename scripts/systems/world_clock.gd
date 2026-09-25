extends Node
## Autoload: shared day/night clock. The sun/sky rig reads `time_of_day`
## each frame; other systems (spawns, NPC schedules later) can subscribe
## to `hour_passed` instead of polling.

signal hour_passed(hour: int)

@export var day_length_seconds: float = 300.0 ## real seconds per in-game day
@export var start_hour: float = 8.0

var time_of_day: float = 8.0 ## 0..24, wraps

var _last_hour: int = -1

func _ready() -> void:
	time_of_day = start_hour
	_last_hour = int(time_of_day)

func _process(delta: float) -> void:
	var hours_per_second := 24.0 / day_length_seconds
	time_of_day = fmod(time_of_day + hours_per_second * delta, 24.0)
	var hour := int(time_of_day)
	if hour != _last_hour:
		_last_hour = hour
		hour_passed.emit(hour)

func is_night() -> bool:
	return time_of_day < 5.5 or time_of_day > 19.5

## 0 at midnight, 1 at noon — handy for lighting curves.
func sun_height_factor() -> float:
	return (cos((time_of_day / 24.0) * TAU) * -0.5) + 0.5
