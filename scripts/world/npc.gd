extends Node3D
## One townsperson: a customised npc_*.glb that either strolls between street
## intersections, chats in place, or minds a shop door. Far from the camera it
## hides and stops animating so 200+ of them stay cheap.

const WALK_SPEED := 1.35
const VIS_DISTANCE := 110.0

var town: Node
var _model: Node3D
var _anim: AnimationPlayer
var _rng := RandomNumberGenerator.new()
var _target_wp := -1
var _target := Vector3.ZERO
var _lane := 0.0
var _wait := 0.0
var _vendor := false
var _vis_timer := 0.0
var _visible_now := true

func setup(scene: PackedScene, look: Dictionary, p_town: Node, seed_value: int) -> void:
	town = p_town
	_rng.seed = seed_value
	_model = scene.instantiate()
	add_child(_model)
	CharacterLooks.apply(_model, look)
	_anim = _find_anim(_model)
	if _anim:
		for n in ["idle", "walk", "talk", "wave"]:
			if _anim.has_animation(n):
				_anim.get_animation(n).loop_mode = Animation.LOOP_LINEAR
	for gi in _model.find_children("*", "GeometryInstance3D", true, false):
		var g := gi as GeometryInstance3D
		g.visibility_range_end = VIS_DISTANCE
		g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_lane = _rng.randf_range(-3.0, 3.0)

func wander_from(wp: int) -> void:
	global_position = town.waypoint(wp) + Vector3(_lane, 0, _rng.randf_range(-12.0, 12.0))
	_target_wp = wp
	_pick_next()

func become_vendor(pos: Vector3, yaw: float) -> void:
	_vendor = true
	global_position = pos
	rotation.y = yaw
	_play("talk" if _rng.randf() < 0.5 else "idle", _rng.randf_range(0.8, 1.1))

func _pick_next() -> void:
	_target_wp = town.random_neighbor(_target_wp, _rng)
	var p: Vector3 = town.waypoint(_target_wp)
	var dir := (p - global_position)
	dir.y = 0.0
	var side := Vector3(-dir.z, 0.0, dir.x).normalized()
	_target = p + side * _lane
	_play("walk", _rng.randf_range(0.85, 1.1))

func _process(delta: float) -> void:
	_vis_timer -= delta
	if _vis_timer <= 0.0:
		_vis_timer = 0.4 + _rng.randf() * 0.2
		var cam := get_viewport().get_camera_3d()
		var near := cam == null or cam.global_position.distance_to(global_position) < VIS_DISTANCE
		if near != _visible_now:
			_visible_now = near
			if _anim:
				_anim.active = near
	if _vendor:
		return
	if _wait > 0.0:
		_wait -= delta
		if _wait <= 0.0:
			_pick_next()
		return
	var to := _target - global_position
	to.y = 0.0
	var dist := to.length()
	if dist < 0.4:
		# pause at the corner: look around, chat or wave
		_wait = _rng.randf_range(1.5, 7.0)
		var r := _rng.randf()
		_play("talk" if r < 0.35 else ("wave" if r < 0.45 else "idle"), 1.0)
		return
	var step := minf(WALK_SPEED * delta, dist)
	global_position += to / dist * step
	rotation.y = lerp_angle(rotation.y, atan2(to.x, to.z), minf(1.0, delta * 6.0))

func _play(name: String, speed: float) -> void:
	if _anim and _anim.has_animation(name):
		_anim.speed_scale = speed
		if _anim.current_animation != name:
			_anim.play(name, 0.25)

func _find_anim(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var f := _find_anim(c)
		if f:
			return f
	return null
