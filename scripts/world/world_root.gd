extends Node3D
## Wires the player into the terrain streamer, drops them on dry ground at
## spawn, dresses the spawn clearing, and keeps the lake surface and the
## distant mountain backdrop centred on the player.

const Streamer := preload("res://scripts/world/world_streamer.gd")
const SPAWN_SEARCH_STEP := 12.0
const UNSTUCK_DEPTH := 4.0
const BACKDROP_RADIUS := 620.0
const BACKDROP_PEAKS := 9

@onready var streamer: Node3D = $WorldStreamer
@onready var player: CharacterBody3D = $Player
@onready var water: MeshInstance3D = $Water
@onready var backdrop: Node3D = $Backdrop

func _ready() -> void:
	var spawn := _find_dry_spawn(Vector2.ZERO)
	player.global_position = Vector3(spawn.x, streamer.height_at(spawn.x, spawn.y) + 1.0, spawn.y)
	player.velocity = Vector3.ZERO
	streamer.set_target(player)
	water.position.y = Streamer.WATER_LEVEL
	_dress_spawn(spawn)
	_build_backdrop()
	var town := get_node_or_null("Town")
	if town:
		town.setup(streamer, player)

func _physics_process(_delta: float) -> void:
	var p := player.global_position
	water.global_position = Vector3(snappedf(p.x, 16.0), Streamer.WATER_LEVEL, snappedf(p.z, 16.0))
	backdrop.global_position = Vector3(p.x, 0.0, p.z)
	# Safety net: if the player ever ends up under the terrain (tunnelling
	# at high fall speed, a chunk rebuilt underneath them), put them back
	# on top instead of leaving them stuck falling forever.
	var ground: float = streamer.height_at(p.x, p.z)
	if p.y < ground - UNSTUCK_DEPTH:
		player.global_position = Vector3(p.x, ground + 1.0, p.z)
		player.velocity = Vector3.ZERO

## Spirals outward from `origin` until it finds grassland above the water
## line, so a fresh game never starts at the bottom of a lake.
func _find_dry_spawn(origin: Vector2) -> Vector2:
	for ring in range(0, 40):
		var steps := maxi(1, ring * 6)
		for i in range(steps):
			var a := TAU * float(i) / steps
			var c := origin + Vector2(cos(a), sin(a)) * ring * SPAWN_SEARCH_STEP
			var h: float = streamer.height_at(c.x, c.y)
			if h > Streamer.WATER_LEVEL + 1.5 and h < Streamer.ROCK_HEIGHT - 1.0 and streamer.slope_at(c.x, c.y) < 0.2:
				return c
	return origin

## A small shrine by the spawn point so the first view has a destination.
func _dress_spawn(spawn: Vector2) -> void:
	var root := Node3D.new()
	root.name = "SpawnShrine"
	add_child(root)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var gate_pos := spawn + Vector2(0.0, -16.0)
	_place(root, "mountain_gate", gate_pos, 0.0, Vector2.ZERO)
	for side in [-1.0, 1.0]:
		_place(root, "guardian_lion", gate_pos + Vector2(side * 6.5, 2.5), 0.0, Vector2(0.9, 2.5))
		for k in range(3):
			_place(root, "stone_lantern_a", spawn + Vector2(side * 3.2, -2.0 - k * 4.5), 0.0, Vector2(0.4, 1.8))
		_place(root, "cherry_tree_%s" % ["a", "b"][int(side > 0.0)], spawn + Vector2(side * 9.0, -9.0), rng.randf() * TAU, Vector2(0.4, 4.0))
	_place(root, "pagoda_small", gate_pos + Vector2(-2.0, -22.0), 0.0, Vector2(3.0, 6.0))
	_place(root, "pavilion_square", spawn + Vector2(14.0, 6.0), 0.4, Vector2(1.0, 4.0))
	_place(root, "banner_pole_a", gate_pos + Vector2(-9.0, 1.0), 0.0, Vector2.ZERO)
	_place(root, "banner_pole_b", gate_pos + Vector2(9.0, 1.0), PI, Vector2.ZERO)
	_place(root, "spirit_stone_cluster_a", spawn + Vector2(-7.0, 5.0), 0.3, Vector2.ZERO)
	_place(root, "maple_tree_a", spawn + Vector2(-15.0, 3.0), 1.0, Vector2(0.4, 4.0))
	_place(root, "boulder_a", spawn + Vector2(-11.0, 9.0), 2.0, Vector2(1.2, 1.6))

func _place(parent: Node3D, model: String, at: Vector2, yaw: float, col: Vector2) -> void:
	var h: float = streamer.height_at(at.x, at.y)
	streamer.place(parent, model, Vector3(at.x, h - 0.2, at.y), yaw, 1.0, col, 800.0)

## Ring of huge snow-capped peaks far beyond the streamed terrain.
func _build_backdrop() -> void:
	var scene: PackedScene = load("res://assets/models/distant_peak.glb")
	var rng := RandomNumberGenerator.new()
	rng.seed = 99
	for i in range(BACKDROP_PEAKS):
		var a := TAU * float(i) / BACKDROP_PEAKS + rng.randf_range(-0.2, 0.2)
		var peak: Node3D = scene.instantiate()
		backdrop.add_child(peak)
		var r := BACKDROP_RADIUS * rng.randf_range(0.9, 1.25)
		peak.position = Vector3(cos(a) * r, rng.randf_range(-14.0, -4.0), sin(a) * r)
		peak.rotation.y = rng.randf_range(0.0, TAU)
		var s := rng.randf_range(2.2, 3.4)
		peak.scale = Vector3(s, s * rng.randf_range(0.9, 1.4), s)
