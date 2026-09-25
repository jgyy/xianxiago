class_name SunLight
extends DirectionalLight3D
## Rotates and recolors the sun according to WorldClock, driving the
## day/night cycle. Warm sunrise/sunset tones near the horizon, cool dim
## moonlight at night, full brightness at noon.

const NIGHT_COLOR := Color(0.45, 0.55, 0.78)
const HORIZON_COLOR := Color(1.0, 0.55, 0.32)
const DAY_COLOR := Color(1.0, 0.95, 0.88)

@export var max_energy: float = 1.2
@export var night_energy: float = 0.05

func _process(_delta: float) -> void:
	_update()

func _update() -> void:
	var t := WorldClock.time_of_day
	rotation_degrees.x = (t / 24.0) * 360.0 - 90.0

	var height := WorldClock.sun_height_factor()
	light_energy = lerpf(night_energy, max_energy, clampf(height * 1.6, 0.0, 1.0))

	if height < 0.15:
		light_color = NIGHT_COLOR.lerp(HORIZON_COLOR, height / 0.15)
	else:
		light_color = HORIZON_COLOR.lerp(DAY_COLOR, clampf((height - 0.15) / 0.35, 0.0, 1.0))
