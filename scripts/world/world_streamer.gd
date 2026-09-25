class_name WorldStreamer
extends Node3D
## Streams TerrainChunk tiles in around a tracked target, spawning new
## ones and freeing distant ones as the target moves. Chunks share one
## height function so the world is effectively unbounded — this is the
## piece that lets the open world "keep expanding" as the player explores.
##
## Each chunk is dressed from the Blender-generated model library in
## assets/models: biome-aware trees, rocks and spirit props as regular
## instances (big ones get simple colliders), ground cover as MultiMeshes,
## and now and then a landmark (pavilion, pagoda, gate...) with its
## lanterns and banners.

const TerrainChunkScene := preload("res://scenes/world/TerrainChunk.tscn")
const TERRAIN_MATERIAL := preload("res://resources/materials/terrain_material.tres")

const MODEL_DIR := "res://assets/models/%s.glb"

## Shared with terrain.gdshader so props match the painted bands.
const WATER_LEVEL := -2.6
const ROCK_HEIGHT := 8.0
const SNOW_HEIGHT := 19.0

## Azure Cloud Town (see town.gd) sits on a levelled terrace here.
const TOWN_CENTER := Vector2(0.0, -330.0)
const TOWN_HALF_SIZE := 150.0
const TOWN_BLOCK := 44.0
const TOWN_STREET_WIDTH := 8.0
const TOWN_BLEND := 70.0

const PROP_CELL_SIZE := 7.0
const GROUND_COVER_PER_CHUNK := 150
const LANDMARK_CHANCE := 0.16
const SPAWN_CLEAR_RADIUS := 26.0

enum Biome { PINE_FOREST, CHERRY_GROVE, BAMBOO_GROVE, MAPLE_WOODS, MEADOW }

# Scatter library. band: "shore" / "grass" / "rock" / "snow" / "any".
# biomes: which Biome values it appears in ([] = all). col: collider
# (radius, height) in unscaled model units, or Vector2.ZERO for none.
# vis: visibility range end in metres.
const PROPS := [
	{"m": ["pine_tree_a", "pine_tree_b", "pine_tree_c", "pine_tree_d"], "band": "grass", "biomes": [Biome.PINE_FOREST, Biome.MAPLE_WOODS], "w": 9, "s": Vector2(0.8, 1.25), "col": Vector2(0.45, 5.0), "vis": 400.0},
	{"m": ["pine_tree_a", "pine_tree_c"], "band": "rock", "biomes": [], "w": 4, "s": Vector2(0.6, 1.0), "col": Vector2(0.45, 5.0), "vis": 400.0},
	{"m": ["twisted_pine_a", "twisted_pine_b"], "band": "rock", "biomes": [], "w": 3, "s": Vector2(0.9, 1.3), "col": Vector2(0.5, 3.0), "vis": 320.0},
	{"m": ["cherry_tree_a", "cherry_tree_b", "cherry_tree_c"], "band": "grass", "biomes": [Biome.CHERRY_GROVE, Biome.MEADOW], "w": 9, "s": Vector2(0.85, 1.2), "col": Vector2(0.4, 4.0), "vis": 380.0},
	{"m": ["maple_tree_a", "maple_tree_b", "maple_tree_c"], "band": "grass", "biomes": [Biome.MAPLE_WOODS], "w": 9, "s": Vector2(0.85, 1.25), "col": Vector2(0.4, 4.0), "vis": 380.0},
	{"m": ["ginkgo_tree_a", "ginkgo_tree_b"], "band": "grass", "biomes": [Biome.MAPLE_WOODS, Biome.MEADOW], "w": 3, "s": Vector2(0.9, 1.2), "col": Vector2(0.4, 4.0), "vis": 380.0},
	{"m": ["willow_tree_a", "willow_tree_b"], "band": "shore", "biomes": [], "w": 6, "s": Vector2(0.9, 1.2), "col": Vector2(0.5, 4.0), "vis": 380.0},
	{"m": ["bamboo_cluster_a", "bamboo_cluster_b", "bamboo_cluster_c"], "band": "grass", "biomes": [Biome.BAMBOO_GROVE], "w": 14, "s": Vector2(0.8, 1.2), "col": Vector2(0.9, 4.0), "vis": 320.0},
	{"m": ["dead_tree_a", "dead_tree_b"], "band": "rock", "biomes": [], "w": 1, "s": Vector2(0.8, 1.1), "col": Vector2(0.35, 3.0), "vis": 320.0},
	{"m": ["dead_tree_a"], "band": "snow", "biomes": [], "w": 1, "s": Vector2(0.7, 1.0), "col": Vector2(0.35, 3.0), "vis": 320.0},
	{"m": ["bush_a", "bush_b", "bush_c"], "band": "grass", "biomes": [], "w": 5, "s": Vector2(0.8, 1.4), "col": Vector2.ZERO, "vis": 160.0},
	{"m": ["boulder_a", "boulder_b", "boulder_c", "boulder_d", "boulder_e", "boulder_f"], "band": "any", "biomes": [], "w": 4, "s": Vector2(0.6, 1.6), "col": Vector2(1.2, 1.6), "vis": 300.0},
	{"m": ["cliff_spire_a", "cliff_spire_b"], "band": "rock", "biomes": [], "w": 2, "s": Vector2(0.8, 1.3), "col": Vector2(1.4, 8.0), "vis": 500.0},
	{"m": ["cliff_spire_c", "cliff_spire_d"], "band": "snow", "biomes": [], "w": 3, "s": Vector2(0.9, 1.4), "col": Vector2(1.4, 8.0), "vis": 500.0},
	{"m": ["spirit_stone_cluster_a", "spirit_stone_cluster_b", "spirit_stone_cluster_c"], "band": "any", "biomes": [], "w": 1, "s": Vector2(0.8, 1.3), "col": Vector2.ZERO, "vis": 180.0},
	{"m": ["jade_crystal_formation"], "band": "rock", "biomes": [], "w": 1, "s": Vector2(0.7, 1.0), "col": Vector2(1.5, 2.5), "vis": 260.0},
	{"m": ["mushroom_cluster_a", "mushroom_cluster_b"], "band": "grass", "biomes": [Biome.PINE_FOREST, Biome.MAPLE_WOODS, Biome.BAMBOO_GROVE], "w": 2, "s": Vector2(0.8, 1.4), "col": Vector2.ZERO, "vis": 90.0},
	{"m": ["spirit_herb_a", "spirit_herb_b"], "band": "grass", "biomes": [], "w": 1, "s": Vector2(1.0, 1.4), "col": Vector2.ZERO, "vis": 90.0},
	{"m": ["stone_lantern_a", "stone_lantern_b"], "band": "grass", "biomes": [], "w": 1, "s": Vector2(0.9, 1.1), "col": Vector2(0.4, 1.8), "vis": 200.0},
	{"m": ["stele_a", "stele_b", "sword_in_stone"], "band": "any", "biomes": [], "w": 1, "s": Vector2(0.9, 1.1), "col": Vector2(0.7, 3.0), "vis": 220.0},
	{"m": ["reeds", "lotus_pads"], "band": "shore", "biomes": [], "w": 5, "s": Vector2(0.9, 1.3), "col": Vector2.ZERO, "vis": 140.0},
	{"m": ["stepping_stones"], "band": "shore", "biomes": [], "w": 1, "s": Vector2(1.0, 1.0), "col": Vector2.ZERO, "vis": 160.0},
	{"m": ["rock_arch"], "band": "rock", "biomes": [], "w": 1, "s": Vector2(0.9, 1.2), "col": Vector2.ZERO, "vis": 400.0},
]

# MultiMesh ground cover per band.
const GROUND_COVER := {
	"grass": ["grass_tuft_a", "grass_tuft_b", "grass_tuft_c", "grass_tuft_d", "flower_patch_a", "flower_patch_b", "flower_patch_c", "fern_a", "fern_b"],
	"shore": ["grass_tuft_a", "grass_tuft_b", "reeds"],
	"rock": ["grass_tuft_a", "fern_a"],
}
const GROUND_COVER_RANGE := 80.0

# Landmark sets: a centrepiece plus dressing placed around it.
const LANDMARKS := [
	{"centre": "pavilion_square", "radius": 6.0, "dress": ["stone_lantern_a", "stone_lantern_a", "banner_pole_a", "incense_burner"]},
	{"centre": "pavilion_hex", "radius": 6.0, "dress": ["hanging_lantern", "hanging_lantern", "scroll_table", "wine_gourd"]},
	{"centre": "pagoda_small", "radius": 7.0, "dress": ["stone_lantern_c", "stone_lantern_c", "prayer_flags", "incense_burner"]},
	{"centre": "pagoda_tall", "radius": 8.0, "dress": ["stone_pillar_a", "stone_pillar_b", "banner_pole_b", "stone_lantern_b"]},
	{"centre": "shrine_gate", "radius": 5.0, "dress": ["talisman_post", "talisman_post", "stone_lantern_a", "guardian_lion"]},
	{"centre": "mountain_gate", "radius": 7.0, "dress": ["guardian_lion", "guardian_lion", "banner_pole_a", "banner_pole_b"]},
	{"centre": "bell_tower", "radius": 5.0, "dress": ["stone_lantern_b", "crate_stack", "barrel_stack"]},
	{"centre": "sect_hall", "radius": 11.0, "dress": ["stone_stairs", "guardian_lion", "guardian_lion", "weapon_rack", "banner_pole_a", "banner_pole_b"]},
	{"centre": "meditation_platform", "radius": 5.0, "dress": ["qi_orb_shrine", "lotus_flower_glow", "spirit_herb_a"]},
	{"centre": "spirit_well", "radius": 4.0, "dress": ["alchemy_cauldron", "barrel_stack", "crate_stack", "hanging_lantern"]},
	{"centre": "stone_arch", "radius": 6.0, "dress": ["stone_pillar_a", "stone_pillar_b", "stele_a"]},
	{"centre": "wall_segment", "radius": 6.0, "dress": ["wall_corner", "stone_lantern_a", "arched_bridge"]},
	{"centre": "plank_bridge", "radius": 7.0, "dress": ["prayer_flags", "banner_pole_b"]},
]
const SKY_PROPS := ["floating_isle_a", "floating_isle_b", "cloud_platform"]

@export var chunk_size: float = 64.0
@export var chunk_resolution: int = 40
@export var height_scale: float = 14.0
@export var mountain_height: float = 42.0
@export var view_distance_chunks: int = 4
@export var noise_seed: int = 1337
@export var noise_frequency: float = 0.012

var _noise: FastNoiseLite
var _mountain_noise: FastNoiseLite
var _biome_noise: FastNoiseLite
var _loaded_chunks: Dictionary = {} # Vector2i -> TerrainChunk
var _target: Node3D
var _last_center: Vector2i = Vector2i(1 << 20, 1 << 20)
var _scenes: Dictionary = {} # model name -> PackedScene
var _cover_meshes: Dictionary = {} # model name -> Mesh

func _ready() -> void:
	_noise = FastNoiseLite.new()
	_noise.seed = noise_seed
	_noise.frequency = noise_frequency
	_noise.noise_type = FastNoiseLite.TYPE_PERLIN
	_noise.fractal_octaves = 5
	_noise.fractal_gain = 0.5

	_mountain_noise = FastNoiseLite.new()
	_mountain_noise.seed = noise_seed + 7
	_mountain_noise.frequency = 0.0035
	_mountain_noise.noise_type = FastNoiseLite.TYPE_PERLIN
	_mountain_noise.fractal_octaves = 4

	_biome_noise = FastNoiseLite.new()
	_biome_noise.seed = noise_seed + 21
	_biome_noise.frequency = 0.004
	_biome_noise.noise_type = FastNoiseLite.TYPE_CELLULAR
	_biome_noise.cellular_return_type = FastNoiseLite.RETURN_CELL_VALUE

func set_target(target: Node3D) -> void:
	_target = target
	_update_chunks()

func _process(_delta: float) -> void:
	if _target:
		_update_chunks()

## Height of the generated terrain at an arbitrary world XZ position;
## used to build chunks and to place the player and props on the ground.
func height_at(world_x: float, world_z: float) -> float:
	if _noise == null:
		return 0.0
	var natural := _natural_height(world_x, world_z)
	var t := smoothstep(TOWN_HALF_SIZE + 15.0, TOWN_HALF_SIZE + TOWN_BLEND, town_distance(world_x, world_z))
	return lerpf(town_height(), natural, t)

func _natural_height(world_x: float, world_z: float) -> float:
	var base := _noise.get_noise_2d(world_x, world_z) * height_scale
	var m := _mountain_noise.get_noise_2d(world_x, world_z)
	var ridge := smoothstep(0.08, 0.5, m)
	return base + pow(ridge, 1.6) * mountain_height

## Square (Chebyshev) distance from the town centre, in metres.
func town_distance(world_x: float, world_z: float) -> float:
	return maxf(absf(world_x - TOWN_CENTER.x), absf(world_z - TOWN_CENTER.y))

## Height of the town terrace: the natural ground at the centre, kept
## comfortably above the lakes and below the snow line.
func town_height() -> float:
	if _noise == null:
		return 3.0
	return clampf(_natural_height(TOWN_CENTER.x, TOWN_CENTER.y), WATER_LEVEL + 3.5, ROCK_HEIGHT - 2.0)

func slope_at(world_x: float, world_z: float) -> float:
	var e := 1.0
	var dx := height_at(world_x + e, world_z) - height_at(world_x - e, world_z)
	var dz := height_at(world_x, world_z + e) - height_at(world_x, world_z - e)
	var n := Vector3(-dx, 2.0 * e, -dz).normalized()
	return 1.0 - n.y

func biome_at(world_x: float, world_z: float) -> int:
	var v := _biome_noise.get_noise_2d(world_x, world_z) * 0.5 + 0.5
	return clampi(int(v * 5.0), 0, 4)

func band_at(h: float, slope: float) -> String:
	if h < WATER_LEVEL:
		return "water"
	if h < WATER_LEVEL + 1.4:
		return "shore"
	if h > SNOW_HEIGHT and slope < 0.5:
		return "snow"
	if h > ROCK_HEIGHT or slope > 0.3:
		return "rock"
	return "grass"

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
	chunk.build(coord, chunk_size, chunk_resolution, height_at, TERRAIN_MATERIAL)
	_loaded_chunks[coord] = chunk
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(Vector3i(coord.x, coord.y, noise_seed))
	_scatter_props(coord, chunk, rng)
	_scatter_ground_cover(coord, chunk, rng)
	_maybe_landmark(coord, chunk, rng)

func _world_to_chunk(world_pos: Vector3) -> Vector2i:
	return Vector2i(floori(world_pos.x / chunk_size), floori(world_pos.z / chunk_size))

func _scene(model: String) -> PackedScene:
	if not _scenes.has(model):
		var scene: PackedScene = load(MODEL_DIR % model)
		_scenes[model] = scene
		var probe := scene.instantiate()
		_tune_materials(probe)
		probe.free()
	return _scenes[model]

## Imported glTF materials are shared resources, so tuning them once per
## model affects every instance: a lower scissor threshold keeps cut-out
## foliage from thinning out at a distance, where mipmaps average alpha down.
func _tune_materials(node: Node) -> void:
	if node is MeshInstance3D:
		var mesh := (node as MeshInstance3D).mesh
		if mesh:
			for i in range(mesh.get_surface_count()):
				var mat := mesh.surface_get_material(i) as BaseMaterial3D
				if mat and mat.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
					mat.alpha_scissor_threshold = 0.3
	for child in node.get_children():
		_tune_materials(child)

## Places one model instance (local to chunk) with optional collider and a
## visibility range so far-away dressing costs nothing.
func place(parent: Node3D, model: String, local_pos: Vector3, yaw: float, s: float, col: Vector2, vis: float) -> Node3D:
	var instance: Node3D = _scene(model).instantiate()
	parent.add_child(instance)
	instance.position = local_pos
	instance.rotation.y = yaw
	instance.scale = Vector3(s, s, s)
	_set_visibility(instance, vis)
	if col != Vector2.ZERO:
		var body := StaticBody3D.new()
		var shape := CollisionShape3D.new()
		var cyl := CylinderShape3D.new()
		cyl.radius = col.x * s
		cyl.height = col.y * s
		shape.shape = cyl
		shape.position = Vector3(0.0, cyl.height * 0.5, 0.0)
		body.add_child(shape)
		body.position = local_pos
		parent.add_child(body)
	return instance

func _set_visibility(node: Node, vis: float) -> void:
	if node is GeometryInstance3D:
		var gi := node as GeometryInstance3D
		gi.visibility_range_end = vis
		gi.visibility_range_end_margin = vis * 0.1
		gi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		if vis < 150.0:
			gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for child in node.get_children():
		_set_visibility(child, vis)

## Trees/rocks/landmarks across a freshly built chunk. Placement is a
## deterministic grid jittered per-cell and seeded from the chunk's own
## coordinate, so re-entering a chunk always regenerates the same dressing.
func _scatter_props(coord: Vector2i, chunk: Node3D, rng: RandomNumberGenerator) -> void:
	var origin_x := coord.x * chunk_size
	var origin_z := coord.y * chunk_size
	var cell_count := int(chunk_size / PROP_CELL_SIZE)

	for cz in range(cell_count):
		for cx in range(cell_count):
			var local_x := (cx + rng.randf_range(0.1, 0.9)) * PROP_CELL_SIZE
			var local_z := (cz + rng.randf_range(0.1, 0.9)) * PROP_CELL_SIZE
			var wx := origin_x + local_x
			var wz := origin_z + local_z
			var biome := biome_at(wx, wz)
			# forests are dense, meadows open
			var density := 0.18 if biome == Biome.MEADOW else 0.42
			if rng.randf() > density:
				continue
			if Vector2(wx, wz).length() < SPAWN_CLEAR_RADIUS or town_distance(wx, wz) < TOWN_HALF_SIZE + 25.0:
				continue
			var h := height_at(wx, wz)
			var band := band_at(h, slope_at(wx, wz))
			if band == "water":
				continue
			var entry := _pick_prop(rng, band, biome)
			if entry.is_empty():
				continue
			var models: Array = entry["m"]
			var model: String = models[rng.randi() % models.size()]
			var s := rng.randf_range(entry["s"].x, entry["s"].y)
			place(chunk, model, Vector3(local_x, h - 0.05, local_z), rng.randf_range(0.0, TAU), s, entry["col"], entry["vis"])

	# rare floating islands / cloud platforms drifting above the valleys
	if rng.randf() < 0.12 and town_distance(origin_x + chunk_size * 0.5, origin_z + chunk_size * 0.5) > TOWN_HALF_SIZE + 80.0:
		var lx := rng.randf_range(8.0, chunk_size - 8.0)
		var lz := rng.randf_range(8.0, chunk_size - 8.0)
		var gy := height_at(origin_x + lx, origin_z + lz)
		var model: String = SKY_PROPS[rng.randi() % SKY_PROPS.size()]
		place(chunk, model, Vector3(lx, maxf(gy, WATER_LEVEL) + rng.randf_range(18.0, 34.0), lz), rng.randf_range(0.0, TAU), rng.randf_range(0.8, 1.3), Vector2.ZERO, 600.0)

func _pick_prop(rng: RandomNumberGenerator, band: String, biome: int) -> Dictionary:
	var candidates: Array = []
	var total_weight := 0
	for entry in PROPS:
		if entry["band"] != "any" and entry["band"] != band:
			continue
		var biomes: Array = entry["biomes"]
		if not biomes.is_empty() and not biomes.has(biome):
			continue
		candidates.append(entry)
		total_weight += entry["w"]
	if candidates.is_empty():
		return {}

	var roll := rng.randf() * total_weight
	var cumulative := 0
	for entry in candidates:
		cumulative += entry["w"]
		if roll <= cumulative:
			return entry
	return candidates[-1]

func _cover_mesh(model: String) -> Mesh:
	if _cover_meshes.has(model):
		return _cover_meshes[model]
	var inst := _scene(model).instantiate()
	var mesh: Mesh = null
	var stack: Array = [inst]
	while not stack.is_empty() and mesh == null:
		var n: Node = stack.pop_back()
		if n is MeshInstance3D:
			mesh = (n as MeshInstance3D).mesh
		stack.append_array(n.get_children())
	inst.free()
	_cover_meshes[model] = mesh
	return mesh

## Grass tufts, flowers and ferns as one MultiMesh per model per chunk.
func _scatter_ground_cover(coord: Vector2i, chunk: Node3D, rng: RandomNumberGenerator) -> void:
	var origin_x := coord.x * chunk_size
	var origin_z := coord.y * chunk_size
	var by_model: Dictionary = {}
	for i in range(GROUND_COVER_PER_CHUNK):
		var lx := rng.randf() * chunk_size
		var lz := rng.randf() * chunk_size
		var h := height_at(origin_x + lx, origin_z + lz)
		var band := band_at(h, slope_at(origin_x + lx, origin_z + lz))
		if town_distance(origin_x + lx, origin_z + lz) < TOWN_HALF_SIZE + 5.0:
			continue
		if not GROUND_COVER.has(band):
			continue
		var options: Array = GROUND_COVER[band]
		var model: String = options[rng.randi() % options.size()]
		var basis := Basis(Vector3.UP, rng.randf_range(0.0, TAU)).scaled(Vector3.ONE * rng.randf_range(0.55, 1.0))
		if not by_model.has(model):
			by_model[model] = []
		by_model[model].append(Transform3D(basis, Vector3(lx, h - 0.03, lz)))
	for model in by_model.keys():
		var mesh := _cover_mesh(model)
		_scene(model)  # make sure its materials were tuned
		if mesh == null:
			continue
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		var xforms: Array = by_model[model]
		mm.instance_count = xforms.size()
		for i in range(xforms.size()):
			mm.set_instance_transform(i, xforms[i])
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi.visibility_range_end = GROUND_COVER_RANGE
		mmi.visibility_range_end_margin = 12.0
		mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		chunk.add_child(mmi)

func _maybe_landmark(coord: Vector2i, chunk: Node3D, rng: RandomNumberGenerator) -> void:
	if rng.randf() > LANDMARK_CHANCE:
		return
	var origin_x := coord.x * chunk_size
	var origin_z := coord.y * chunk_size
	var lx := rng.randf_range(16.0, chunk_size - 16.0)
	var lz := rng.randf_range(16.0, chunk_size - 16.0)
	var wx := origin_x + lx
	var wz := origin_z + lz
	if Vector2(wx, wz).length() < SPAWN_CLEAR_RADIUS + 12.0 or town_distance(wx, wz) < TOWN_HALF_SIZE + 60.0:
		return
	var h := height_at(wx, wz)
	if band_at(h, slope_at(wx, wz)) != "grass":
		return
	var lm: Dictionary = LANDMARKS[rng.randi() % LANDMARKS.size()]
	place_landmark(chunk, lm, Vector3(lx, h, lz), rng.randf_range(0.0, TAU), origin_x, origin_z, rng)

func place_landmark(parent: Node3D, lm: Dictionary, local_pos: Vector3, yaw: float, origin_x: float, origin_z: float, rng: RandomNumberGenerator) -> void:
	var r: float = lm["radius"]
	place(parent, lm["centre"], local_pos - Vector3(0, 0.3, 0), yaw, 1.0, Vector2(r * 0.35, 4.0), 700.0)
	var dress: Array = lm["dress"]
	for i in range(dress.size()):
		var a := yaw + (float(i) / dress.size()) * TAU + 0.4
		var off := Vector3(cos(a), 0.0, sin(a)) * (r + rng.randf_range(1.0, 3.0))
		var p := local_pos + off
		p.y = height_at(origin_x + p.x, origin_z + p.z) - 0.05
		place(parent, dress[i], p, a + PI, 1.0, Vector2(0.45, 2.0), 260.0)
