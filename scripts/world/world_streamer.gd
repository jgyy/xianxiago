class_name WorldStreamer
extends Node3D
## Streams TerrainChunk tiles in around a tracked target, spawning new
## ones and freeing distant ones as the target moves. Chunks share one
## FastNoiseLite so the world is effectively unbounded — this is the
## piece that lets the open world "keep expanding" as the player explores.

const TerrainChunkScene := preload("res://scenes/world/TerrainChunk.tscn")

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
	var chunk: TerrainChunk = TerrainChunkScene.instantiate()
	add_child(chunk)
	chunk.build(coord, chunk_size, chunk_resolution, _noise, height_scale, _material)
	_loaded_chunks[coord] = chunk

func _world_to_chunk(world_pos: Vector3) -> Vector2i:
	return Vector2i(floori(world_pos.x / chunk_size), floori(world_pos.z / chunk_size))
