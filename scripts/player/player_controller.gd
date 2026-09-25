extends CharacterBody3D
## Third-person cultivator movement: walk/sprint, jump, and a qinggong
## ("light-body technique") air leap + glide, both powered by QiSystem.

@export_group("Movement")
@export var walk_speed: float = 4.5
@export var sprint_speed: float = 8.5
@export var ground_acceleration: float = 14.0
@export var air_acceleration: float = 5.0
@export var jump_velocity: float = 6.0

@export_group("Qinggong (Light-Body Technique)")
@export var leap_velocity: float = 9.5
@export var leap_qi_cost: float = 20.0
@export var glide_fall_speed: float = 2.2
@export var glide_qi_cost_per_second: float = 10.0

@export_group("Resource Costs")
@export var sprint_qi_cost_per_second: float = 8.0

@export_group("Camera")
@export var mouse_sensitivity: float = 0.0025
@export var pitch_min_deg: float = -70.0
@export var pitch_max_deg: float = 60.0

@onready var camera_pivot: Node3D = $CameraPivot
@onready var spring_arm: SpringArm3D = $CameraPivot/SpringArm3D
@onready var visual: Node3D = $Visual

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity", 9.8)
var _mouse_captured: bool = true
var _used_air_leap: bool = false
var _is_gliding: bool = false

func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	spring_arm.rotation.x = deg_to_rad(-15.0)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and _mouse_captured:
		camera_pivot.rotate_y(-event.relative.x * mouse_sensitivity)
		spring_arm.rotate_x(-event.relative.y * mouse_sensitivity)
		spring_arm.rotation.x = clampf(
			spring_arm.rotation.x, deg_to_rad(pitch_min_deg), deg_to_rad(pitch_max_deg)
		)
	if event.is_action_pressed("toggle_mouse_capture"):
		_mouse_captured = not _mouse_captured
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if _mouse_captured else Input.MOUSE_MODE_VISIBLE

func _physics_process(delta: float) -> void:
	_apply_gravity_or_glide(delta)
	_handle_jump_and_leap()
	_handle_horizontal_movement(delta)

	move_and_slide()

	if is_on_floor():
		_used_air_leap = false
		_is_gliding = false

func _apply_gravity_or_glide(delta: float) -> void:
	if is_on_floor():
		velocity.y = -0.1
		return

	if velocity.y < 0.0 and Input.is_action_pressed("lightbody_glide"):
		var drained := QiSystem.drain(glide_qi_cost_per_second, delta)
		if drained > 0.0:
			_is_gliding = true
			velocity.y = maxf(velocity.y, -glide_fall_speed)
			return

	_is_gliding = false
	velocity.y -= _gravity * delta

func _handle_jump_and_leap() -> void:
	if not Input.is_action_just_pressed("jump"):
		return
	if is_on_floor():
		velocity.y = jump_velocity
	elif not _used_air_leap and QiSystem.try_spend(leap_qi_cost):
		velocity.y = leap_velocity
		_used_air_leap = true

func _handle_horizontal_movement(delta: float) -> void:
	var forward := -camera_pivot.global_transform.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	var right := camera_pivot.global_transform.basis.x
	right.y = 0.0
	right = right.normalized()

	var input_forward := Input.get_action_strength("move_forward") - Input.get_action_strength("move_back")
	var input_right := Input.get_action_strength("move_right") - Input.get_action_strength("move_left")

	var wish_dir := forward * input_forward + right * input_right
	if wish_dir.length() > 1.0:
		wish_dir = wish_dir.normalized()

	var target_speed := walk_speed
	if is_on_floor() and wish_dir.length() > 0.01 and Input.is_action_pressed("sprint"):
		if QiSystem.drain(sprint_qi_cost_per_second, delta) > 0.0:
			target_speed = sprint_speed

	var target_velocity := wish_dir * target_speed
	var accel := ground_acceleration if is_on_floor() else air_acceleration
	var horizontal := Vector3(velocity.x, 0.0, velocity.z).move_toward(target_velocity, accel * delta)
	velocity.x = horizontal.x
	velocity.z = horizontal.z

	if wish_dir.length() > 0.01:
		var target_yaw := atan2(wish_dir.x, wish_dir.z)
		visual.rotation.y = lerp_angle(visual.rotation.y, target_yaw, delta * 10.0)

func is_gliding() -> bool:
	return _is_gliding
