extends Node3D
## Azure Cloud Town: a walled Xianxia market town on a levelled terrace north
## of the spawn shrine. Streets form a grid; every block is lined with
## buildings from assets/buildings (each of the 100+ designs is used at least
## once), the central square holds the civic/temple buildings and market
## stalls, and 220 townsfolk (NPCs built from the customisable npc_*.glb
## models) stroll the streets, mind shops and chat.
##
## The town is only instanced while the player is within LOAD_RADIUS so it
## costs nothing out in the wilds.

const Streamer := preload("res://scripts/world/world_streamer.gd")
const NpcScript := preload("res://scripts/world/npc.gd")
const MANIFEST := "res://assets/buildings/manifest.json"
const BUILDING_DIR := "res://assets/buildings/%s.glb"
const NPC_SCENES := [preload("res://assets/characters/npc_male.glb"), preload("res://assets/characters/npc_female.glb")]

const CENTER := Streamer.TOWN_CENTER
const HALF := Streamer.TOWN_HALF_SIZE      # wall line, metres from centre
const BLOCK := Streamer.TOWN_BLOCK         # street spacing
const STREET := Streamer.TOWN_STREET_WIDTH
const LOAD_RADIUS := 420.0
const UNLOAD_RADIUS := 560.0
const NPC_COUNT := 220

var streamer: Node3D
var player: Node3D
var town_height := 0.0
var _root: Node3D
var _manifest: Array = []
var _scenes: Dictionary = {}
var _waypoints: Array[Vector3] = []   # street intersections (world space)
var _neighbors: Array = []            # waypoint index -> Array[int]
var _door_spots: Array = []           # [position, facing yaw] in front of shops
var building_count := 0
var unique_building_count := 0
var npc_count := 0
var _inside := false

func setup(p_streamer: Node3D, p_player: Node3D) -> void:
	streamer = p_streamer
	player = p_player
	town_height = streamer.town_height()
	if FileAccess.file_exists(MANIFEST):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
		if parsed is Array:
			_manifest = parsed
		elif parsed is Dictionary and parsed.has("buildings"):
			_manifest = parsed["buildings"]

func _process(_delta: float) -> void:
	if player == null:
		return
	var d := Vector2(player.global_position.x, player.global_position.z).distance_to(CENTER)
	if _root == null and d < LOAD_RADIUS:
		build()
	elif _root != null and d > UNLOAD_RADIUS:
		_root.queue_free()
		_root = null
	# announce the town when the player walks through the walls
	var inside: bool = streamer.town_distance(player.global_position.x, player.global_position.z) < HALF
	if inside != _inside:
		_inside = inside
		var hud := get_tree().current_scene.get_node_or_null("HUD") if get_tree().current_scene else null
		if inside and hud and hud.has_method("toast"):
			hud.toast("青云镇 · Azure Cloud Town")

func is_loaded() -> bool:
	return _root != null

func _scene(name: String) -> PackedScene:
	if not _scenes.has(name):
		var path := BUILDING_DIR % name
		_scenes[name] = load(path) if ResourceLoader.exists(path) else null
	return _scenes[name]

func _w(local: Vector2) -> Vector3:
	return Vector3(CENTER.x + local.x, town_height, CENTER.y + local.y)

## Instantiates the whole town. Deterministic: same layout every load.
func build() -> void:
	_root = Node3D.new()
	_root.name = "AzureCloudTown"
	add_child(_root)
	building_count = 0
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260925
	_build_street_graph()

	var by_cat := {}
	for b in _manifest:
		var cat: String = b.get("category", "misc")
		if not by_cat.has(cat):
			by_cat[cat] = []
		by_cat[cat].append(b)
	var lot_pool: Array = []
	for b in _manifest:
		if not (b.get("category", "") in ["wall", "gate"]):
			lot_pool.append(b)
	# each design at least once: shuffled full list first, then random reuse
	var queue: Array = lot_pool.duplicate()
	_shuffle(queue, rng)
	var used := {}

	_place_walls(by_cat, rng, used)

	var n := int(HALF / BLOCK)
	for bz in range(-n, n):
		for bx in range(-n, n):
			var x0 := bx * BLOCK + STREET * 0.5
			var z0 := bz * BLOCK + STREET * 0.5
			var size := BLOCK - STREET
			var centre_block := (bx == -1 or bx == 0) and (bz == -1 or bz == 0)
			if centre_block:
				continue # the town square
			# four street-facing sides of the block: [start, direction, outward normal]
			var sides := [
				[Vector2(x0, z0), Vector2(1, 0), Vector2(0, -1)],
				[Vector2(x0 + size, z0 + size), Vector2(-1, 0), Vector2(0, 1)],
				[Vector2(x0, z0 + size), Vector2(0, -1), Vector2(-1, 0)],
				[Vector2(x0 + size, z0), Vector2(0, 1), Vector2(1, 0)],
			]
			for side in sides:
				_fill_side(side[0], side[1], side[2], size, queue, lot_pool, rng, used)
	_fill_square(by_cat, lot_pool, rng, used)
	# anything never placed (unusually large designs) goes in the outer ring
	var leftover: Array = []
	for b in lot_pool:
		if not used.has(b["name"]):
			leftover.append(b)
	_place_leftovers(leftover, rng, used)
	unique_building_count = used.size()
	_spawn_npcs(rng)

func _shuffle(arr: Array, rng: RandomNumberGenerator) -> void:
	for i in range(arr.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t = arr[i]
		arr[i] = arr[j]
		arr[j] = t

func _footprint(b: Dictionary) -> Vector2:
	var f = b.get("footprint", [8, 8])
	return Vector2(float(f[0]), float(f[1]))

func _next_fitting(queue: Array, pool: Array, max_w: float, max_d: float, rng: RandomNumberGenerator) -> Dictionary:
	for i in range(queue.size()):
		var fp := _footprint(queue[i])
		if fp.x <= max_w and fp.y <= max_d:
			var b: Dictionary = queue[i]
			queue.remove_at(i)
			return b
	var fits: Array = []
	for b in pool:
		var fp := _footprint(b)
		if fp.x <= max_w and fp.y <= max_d:
			fits.append(b)
	return fits[rng.randi() % fits.size()] if not fits.is_empty() else {}

## Lines one block side with buildings whose doors face the street.
func _fill_side(start: Vector2, along: Vector2, outward: Vector2, length: float, queue: Array, pool: Array,
		rng: RandomNumberGenerator, used: Dictionary) -> void:
	var t := 1.0
	var max_depth := (BLOCK - STREET) * 0.5 - 1.0
	while t < length - 3.0:
		var b := _next_fitting(queue, pool, length - t - 1.0, max_depth, rng)
		if b.is_empty():
			break
		var fp := _footprint(b)
		var local := start + along * (t + fp.x * 0.5) - outward * (fp.y * 0.5 + 0.6)
		var yaw := atan2(outward.x, outward.y) # model +Z (door) faces the street
		_place_building(b, local, yaw, used)
		t += fp.x + rng.randf_range(0.8, 2.5)

func _place_building(b: Dictionary, local: Vector2, yaw: float, used: Dictionary) -> void:
	var scene := _scene(b["name"])
	if scene == null:
		return
	var inst: Node3D = scene.instantiate()
	_root.add_child(inst)
	inst.position = _w(local)
	inst.rotation.y = yaw
	used[b["name"]] = true
	building_count += 1
	var fp := _footprint(b)
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	var h := float(b.get("height", 6.0))
	box.size = Vector3(fp.x * 0.92, h, fp.y * 0.92)
	shape.shape = box
	shape.position = Vector3(0, h * 0.5, 0)
	body.add_child(shape)
	inst.add_child(body)
	for mi in inst.find_children("*", "GeometryInstance3D", true, false):
		(mi as GeometryInstance3D).visibility_range_end = 420.0
	if b.get("has_sign", false) or b.get("category", "") in ["shop", "stall"]:
		var off = b.get("door_offset", [0.0, fp.y * 0.5])
		var door := Vector3(float(off[0]), 0.0, float(off[1]) + 1.2)
		_door_spots.append([inst.position + door.rotated(Vector3.UP, yaw), yaw + PI])

func _place_walls(by_cat: Dictionary, rng: RandomNumberGenerator, used: Dictionary) -> void:
	var walls: Array = by_cat.get("wall", [])
	var gates: Array = by_cat.get("gate", [])
	var towers: Array = by_cat.get("tower", [])
	for side in range(4):
		var yaw := side * PI * 0.5
		var along := Vector2(cos(-yaw), sin(-yaw))
		var normal := Vector2(-along.y, along.x)
		var t := -HALF + 4.0
		while t < HALF - 4.0:
			var local := along * t + normal * HALF
			var is_gate := absf(t) < 10.0
			var pool: Array = gates if is_gate and not gates.is_empty() else walls
			if pool.is_empty():
				break
			var b: Dictionary = pool[rng.randi() % pool.size()]
			var fp := _footprint(b)
			_place_building(b, local + along * fp.x * 0.5, atan2(normal.x, normal.y) + PI, used)
			t += fp.x
		if not towers.is_empty():
			var tb: Dictionary = towers[side % towers.size()]
			_place_building(tb, normal * HALF + along * HALF, 0.0, used)

## Central square: the grandest civic/temple buildings around a paved plaza
## with market stalls in rows.
func _fill_square(by_cat: Dictionary, pool: Array, rng: RandomNumberGenerator, used: Dictionary) -> void:
	var big: Array = by_cat.get("temple", []) + by_cat.get("civic", [])
	big.sort_custom(func(a, b): return _footprint(a).x * _footprint(a).y > _footprint(b).x * _footprint(b).y)
	var spots := [[Vector2(0, -BLOCK + 14), 0.0], [Vector2(-BLOCK + 14, 0), PI * 0.5], [Vector2(BLOCK - 14, 0), -PI * 0.5]]
	for i in range(mini(spots.size(), big.size())):
		_place_building(big[i], spots[i][0], spots[i][1], used)
	var stalls: Array = by_cat.get("stall", [])
	if stalls.is_empty():
		return
	for row in range(2):
		for k in range(6):
			var b: Dictionary = stalls[(row * 6 + k) % stalls.size()]
			_place_building(b, Vector2(-17.5 + k * 7.0, 6.0 + row * 12.0), PI if row == 0 else 0.0, used)

func _place_leftovers(leftover: Array, rng: RandomNumberGenerator, used: Dictionary) -> void:
	var t := 0.0
	for b in leftover:
		var fp := _footprint(b)
		var ang := t / (HALF * 0.9)
		var local := Vector2(cos(ang), sin(ang)) * (HALF + 14.0 + fp.y * 0.5)
		_place_building(b, local, -ang - PI * 0.5, used)
		t += fp.x + 4.0

func _build_street_graph() -> void:
	_waypoints.clear()
	_neighbors.clear()
	var n := int(HALF / BLOCK)
	var idx := {}
	for z in range(-n, n + 1):
		for x in range(-n, n + 1):
			idx[Vector2i(x, z)] = _waypoints.size()
			_waypoints.append(_w(Vector2(x * BLOCK, z * BLOCK)))
	for key in idx.keys():
		var list: Array[int] = []
		for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			if idx.has(key + d):
				list.append(idx[key + d])
		_neighbors.append(list)

func _spawn_npcs(rng: RandomNumberGenerator) -> void:
	var folk := Node3D.new()
	folk.name = "Townsfolk"
	_root.add_child(folk)
	npc_count = 0
	for i in range(NPC_COUNT):
		var gender := i % 2
		var npc := NpcScript.new()
		npc.name = "NPC_%03d" % i
		folk.add_child(npc)
		var look := CharacterLooks.preset(gender, rng.randi() % CharacterLooks.PRESET_COUNT)
		npc.setup(NPC_SCENES[gender], look, self, rng.randi())
		if i < _door_spots.size() and i % 3 == 0:
			var spot: Array = _door_spots[i]
			npc.become_vendor(spot[0], spot[1])
		else:
			npc.wander_from(rng.randi() % _waypoints.size())
		npc_count += 1

func waypoint(i: int) -> Vector3:
	return _waypoints[i]

func random_neighbor(i: int, rng: RandomNumberGenerator) -> int:
	var list: Array = _neighbors[i]
	return list[rng.randi() % list.size()]
