class_name WorldStreamer
extends Node3D
## Streams TerrainChunk tiles in around a tracked target, spawning new
## ones and freeing distant ones as the target moves. Chunks share one
## FastNoiseLite so the world is effectively unbounded — this is the
## piece that lets the open world "keep expanding" as the player explores.

const TerrainChunkScene := preload("res://scenes/world/TerrainChunk.tscn")

# Mirrors TerrainChunk.ROCK_HEIGHT / SNOW_HEIGHT so scattered props match the
# grass/rock/snow bands the terrain is colored with.
const ROCK_BAND_HEIGHT := 4.5
const SNOW_BAND_HEIGHT := 9.0

const PROP_CELL_SIZE := 8.0
const PROP_DENSITY := 0.25

# band: "grass" (below ROCK_BAND_HEIGHT), "rock" (between the two bands),
# "snow" (above SNOW_BAND_HEIGHT), or "any" (all bands).
const PROP_LIBRARY := [
	{"scene": preload("res://assets/models/pine_tree.glb"), "band": "grass", "weight": 4, "scale": Vector2(0.85, 1.35)},
	{"scene": preload("res://assets/models/bamboo_cluster.glb"), "band": "grass", "weight": 3, "scale": Vector2(0.8, 1.2)},
	{"scene": preload("res://assets/models/dead_tree.glb"), "band": "grass", "weight": 1, "scale": Vector2(0.8, 1.1)},
	{"scene": preload("res://assets/models/mushroom_cluster.glb"), "band": "grass", "weight": 2, "scale": Vector2(0.7, 1.1)},
	{"scene": preload("res://assets/models/grass_tuft.glb"), "band": "grass", "weight": 5, "scale": Vector2(0.8, 1.3)},
	{"scene": preload("res://assets/models/spirit_stone_cluster.glb"), "band": "any", "weight": 1, "scale": Vector2(0.7, 1.2)},
	{"scene": preload("res://assets/models/boulder_rock.glb"), "band": "rock", "weight": 3, "scale": Vector2(0.7, 1.6)},
	{"scene": preload("res://assets/models/stone_pillar.glb"), "band": "rock", "weight": 1, "scale": Vector2(0.9, 1.1)},
	{"scene": preload("res://assets/models/stone_lantern.glb"), "band": "rock", "weight": 1, "scale": Vector2(0.9, 1.1)},
	{"scene": preload("res://assets/models/cliff_spire.glb"), "band": "snow", "weight": 2, "scale": Vector2(0.8, 1.4)},
	{"scene": preload("res://assets/models/shrine_gate.glb"), "band": "grass", "weight": 1, "scale": Vector2(0.9, 1.0)},
	{"scene": preload("res://assets/models/stone_arch.glb"), "band": "rock", "weight": 1, "scale": Vector2(0.8, 1.1)},
]

@export var chunk_size: float = 64.0
@export var chunk_resolution: int = 24
@export var height_scale: float = 14.0
@export var view_distance_chunks: int = 4
@export var noise_seed: int = 1337
@export var noise_frequency: float = 0.015

var _noise: FastNoiseLite
var _material: StandardMaterial3D
var _loaded_chunks: Dictionary = {} # Vector2i -> TerrainChunk
var _target: Node3D
var _last_center: Vector2i = Vector2i(1 << 20, 1 << 20)

func _ready() -> void:
	_noise = FastNoiseLite.new()
	_noise.seed = noise_seed
	_noise.frequency = noise_frequency
	_noise.noise_type = FastNoiseLite.TYPE_PERLIN
	_noise.fractal_octaves = 4
	_noise.fractal_gain = 0.5

	_material = StandardMaterial3D.new()
	_material.vertex_color_use_as_albedo = true
	_material.roughness = 0.9

func set_target(target: Node3D) -> void:
	_target = target
	_update_chunks()

func _process(_delta: float) -> void:
	if _target:
		_update_chunks()

## Height of the generated terrain at an arbitrary world XZ position;
## used to place the player and other objects on load.
func height_at(world_x: float, world_z: float) -> float:
	if _noise == null:
		return 0.0
	return _noise.get_noise_2d(world_x, world_z) * height_scale

func _update_chunks() -> void:
	var center := _world_to_chunk(_target.global_position)
	if center == _last_center and not _loaded_chunks.is_empty():
		return
	_last_center = center

	var needed := {}
	for dz in range(-view_distance_chunks, view_distance_chunks + 1):
		for dx in range(-view_distance_chunks, view_distance_chunks + 1):
			var coord := Vector2i(center.x + dx, center.y + dz)
			needed[coord] = true
			if not _loaded_chunks.has(coord):
				_spawn_chunk(coord)

	for coord in _loaded_chunks.keys():
		if not needed.has(coord):
			_loaded_chunks[coord].queue_free()
			_loaded_chunks.erase(coord)

func _spawn_chunk(coord: Vector2i) -> void:
	var chunk: Node3D = TerrainChunkScene.instantiate()
	add_child(chunk)
	chunk.build(coord, chunk_size, chunk_resolution, _noise, height_scale, _material)
	_loaded_chunks[coord] = chunk
	_scatter_props(coord, chunk)

func _world_to_chunk(world_pos: Vector3) -> Vector2i:
	return Vector2i(floori(world_pos.x / chunk_size), floori(world_pos.z / chunk_size))

## Scatters trees/rocks/landmarks across a freshly built chunk. Placement is
## a deterministic grid jittered per-cell and seeded from the chunk's own
## coordinate, so re-entering a chunk always regenerates the same dressing.
func _scatter_props(coord: Vector2i, chunk: Node3D) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(Vector3i(coord.x, coord.y, noise_seed))

	var origin_x := coord.x * chunk_size
	var origin_z := coord.y * chunk_size
	var cell_count := int(chunk_size / PROP_CELL_SIZE)

	for cz in range(cell_count):
		for cx in range(cell_count):
			if rng.randf() > PROP_DENSITY:
				continue

			var local_x := (cx + rng.randf_range(0.15, 0.85)) * PROP_CELL_SIZE
			var local_z := (cz + rng.randf_range(0.15, 0.85)) * PROP_CELL_SIZE
			var h := height_at(origin_x + local_x, origin_z + local_z)

			var entry := _pick_prop(rng, h)
			if entry.is_empty():
				continue

			var instance: Node3D = entry["scene"].instantiate()
			chunk.add_child(instance)
			instance.position = Vector3(local_x, h, local_z)
			instance.rotation.y = rng.randf_range(0.0, TAU)
			var s := rng.randf_range(entry["scale"].x, entry["scale"].y)
			instance.scale = Vector3(s, s, s)

func _band_for_height(h: float) -> String:
	if h < ROCK_BAND_HEIGHT:
		return "grass"
	if h < SNOW_BAND_HEIGHT:
		return "rock"
	return "snow"

func _pick_prop(rng: RandomNumberGenerator, height: float) -> Dictionary:
	var band := _band_for_height(height)
	var candidates: Array = []
	var total_weight := 0
	for entry in PROP_LIBRARY:
		if entry["band"] == "any" or entry["band"] == band:
			candidates.append(entry)
			total_weight += entry["weight"]
	if candidates.is_empty():
		return {}

	var roll := rng.randf() * total_weight
	var cumulative := 0
	for entry in candidates:
		cumulative += entry["weight"]
		if roll <= cumulative:
			return entry
	return candidates[-1]
