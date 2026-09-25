class_name SunLight
extends DirectionalLight3D
## Rotates and recolors the sun according to WorldClock, driving the
## day/night cycle. Warm sunrise/sunset tones near the horizon, cool dim
## moonlight at night, full brightness at noon. Also retints the fog and
## ambient light so distant hills fade into the sky's own horizon colour
## instead of a fixed grey.

const NIGHT_COLOR := Color(0.66, 0.76, 1.0)
const HORIZON_COLOR := Color(1.0, 0.62, 0.38)
const DAY_COLOR := Color(1.0, 0.96, 0.88)

const FOG_NIGHT := Color(0.22, 0.28, 0.44)
const FOG_DUSK := Color(0.93, 0.66, 0.52)
const FOG_DAY := Color(0.72, 0.82, 0.90)

@export var max_energy: float = 1.35
@export var night_energy: float = 0.7
@export var azimuth_degrees: float = 35.0

var _environment: Environment

func _ready() -> void:
	var env_node := get_parent().get_node_or_null("WorldEnvironment") as WorldEnvironment
	if env_node:
		_environment = env_node.environment

func _process(_delta: float) -> void:
	_update()

func _update() -> void:
	var t := WorldClock.time_of_day
	# 06:00 on the horizon, 12:00 overhead (light pointing straight down),
	# 18:00 setting. Between 18:00 and 06:00 the light flips to act as the
	# moon so the world never goes pitch black.
	var day_angle := (t / 24.0) * 360.0 - 90.0
	var height := WorldClock.sun_height_factor()
	var is_moon := t < 6.0 or t > 18.0
	var elevation := -day_angle if not is_moon else -(day_angle - 180.0)
	rotation_degrees = Vector3(elevation, azimuth_degrees, 0.0)

	if is_moon:
		light_energy = night_energy + 0.1 * (1.0 - absf(height - 0.25) * 4.0)
		light_color = NIGHT_COLOR
	else:
		light_energy = lerpf(night_energy, max_energy, clampf((height - 0.5) * 3.0 + 0.25, 0.0, 1.0))
		var warm := clampf((height - 0.5) / 0.3, 0.0, 1.0)
		light_color = HORIZON_COLOR.lerp(DAY_COLOR, warm)

	if _environment:
		# The sky shader needs the real sun even while this light plays the moon.
		var to_light := global_transform.basis.z.normalized()
		var sky_mat := _environment.sky.sky_material as ShaderMaterial if _environment.sky else null
		if sky_mat:
			sky_mat.set_shader_parameter("sun_dir", -to_light if is_moon else to_light)
		var fog: Color
		if height < 0.4:
			fog = FOG_NIGHT.lerp(FOG_DUSK, smoothstep(0.3, 0.5, height))
		else:
			fog = FOG_DUSK.lerp(FOG_DAY, smoothstep(0.5, 0.75, height))
		if height < 0.35:
			fog = FOG_NIGHT
		_environment.fog_light_color = fog
		_environment.ambient_light_energy = lerpf(2.6, 1.0, smoothstep(0.35, 0.7, height))
