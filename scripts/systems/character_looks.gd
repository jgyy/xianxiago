extends Node
## Autoload: character customisation. The cultivator / NPC models carry every
## hair style and accessory as separate skinned meshes plus tintable material
## slots (M_robe, M_inner, M_sash, M_skin, M_hair, M_boots). A "look" is a
## Dictionary choosing one hair style, a set of accessories, slot colours and
## a height; `apply()` shows/hides meshes and tints materials on an instance.
##
## `preset(gender, i)` gives 100 named, hand-balanced looks per gender
## (i = 0..99), built from Xianxia palettes with a fixed seed so every index
## always produces the same character.

const PRESET_COUNT := 100
const MALE := 0
const FEMALE := 1

const HAIR_STYLES := [
	["topknot", "crowned_knot", "long_loose", "half_up", "headband"],
	["twin_buns", "long_straight", "high_ponytail", "pinned_bun", "side_braid"],
]
const ACCESSORIES := [
	["sword", "beard", "gourd", "hat", "cape"],
	["ribbon", "veil", "flute", "hat", "cape"],
]

## Robe / sash colours: traditional pigment names.
const ROBE_COLORS := {
	"Jade": Color(0.30, 0.68, 0.58), "Celadon": Color(0.62, 0.80, 0.70), "Azure": Color(0.36, 0.58, 0.84),
	"Indigo": Color(0.22, 0.26, 0.52), "Ink": Color(0.16, 0.17, 0.20), "Moon White": Color(0.95, 0.95, 0.92),
	"Vermilion": Color(0.80, 0.22, 0.16), "Peach Blossom": Color(0.98, 0.72, 0.76), "Lotus": Color(0.86, 0.52, 0.66),
	"Apricot": Color(0.98, 0.76, 0.46), "Pine": Color(0.20, 0.40, 0.30), "Plum": Color(0.46, 0.24, 0.44),
	"Sky": Color(0.66, 0.82, 0.94), "Ochre Gold": Color(0.84, 0.64, 0.26), "Crane Grey": Color(0.60, 0.62, 0.64),
	"Cinnabar": Color(0.66, 0.12, 0.12), "Wisteria": Color(0.66, 0.60, 0.86), "Bamboo": Color(0.56, 0.72, 0.40),
}
const HAIR_COLORS := {
	"Ink Black": Color(1.0, 1.0, 1.0), "Raven Blue": Color(0.75, 0.85, 1.35), "Chestnut": Color(2.6, 1.7, 1.2),
	"Silver Frost": Color(7.0, 7.2, 7.6), "Auburn": Color(3.0, 1.4, 1.0),
}
const SKIN_TONES := {
	"Porcelain": Color(1.04, 1.02, 1.02), "Ivory": Color(1.0, 0.97, 0.93), "Honey": Color(0.94, 0.84, 0.74),
	"Wheat": Color(0.88, 0.76, 0.64), "Bronze": Color(0.76, 0.60, 0.48), "Umber": Color(0.60, 0.46, 0.36),
}
const BOOT_COLORS := {"Umber": Color(1, 1, 1), "Black": Color(0.35, 0.35, 0.38), "Grey": Color(1.3, 1.3, 1.35)}

const TITLES_A := ["Azure", "Jade", "Cloud", "Crane", "Lotus", "Pine", "Moon", "Frost", "Crimson", "Mist",
	"Thunder", "Plum", "Willow", "Phoenix", "Silver", "Dawn", "Ink", "Spirit", "Autumn", "Starlit"]
const TITLES_B := [
	["Swordsman", "Hermit", "Scholar", "Wanderer", "Alchemist", "Monk", "Disciple", "Sage", "Blade", "Recluse"],
	["Swordswoman", "Maiden", "Scholar", "Wanderer", "Alchemist", "Priestess", "Disciple", "Sage", "Dancer", "Fairy"],
]

var _mat_cache: Dictionary = {} # "<base rid>|<color>" -> material

func preset(gender: int, index: int) -> Dictionary:
	index = posmod(index, PRESET_COUNT)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(Vector2i(gender, index)) + 7919
	var robe_names := ROBE_COLORS.keys()
	var look := {
		"gender": gender,
		"index": index,
		"name": "%s %s" % [TITLES_A[index % TITLES_A.size()], TITLES_B[gender][(index / TITLES_A.size() + index) % TITLES_B[gender].size()]],
		"hair": HAIR_STYLES[gender][rng.randi() % 5],
		"hair_color": HAIR_COLORS.keys()[mini(rng.randi() % 7, 4)], # mostly black
		"skin": SKIN_TONES.keys()[rng.randi() % SKIN_TONES.size()],
		"robe": robe_names[rng.randi() % robe_names.size()],
		"inner": robe_names[rng.randi() % robe_names.size()],
		"sash": robe_names[rng.randi() % robe_names.size()],
		"boots": BOOT_COLORS.keys()[rng.randi() % BOOT_COLORS.size()],
		"accessories": [],
		"height": rng.randf_range(0.94, 1.06),
	}
	for acc in ACCESSORIES[gender]:
		if rng.randf() < 0.3:
			look["accessories"].append(acc)
	if index == 0: # the default hero looks
		look.merge({"hair": HAIR_STYLES[gender][0], "hair_color": "Ink Black", "skin": "Ivory" if gender == FEMALE else "Wheat",
			"robe": "Moon White" if gender == FEMALE else "Jade", "inner": "Vermilion" if gender == FEMALE else "Moon White",
			"sash": "Indigo" if gender == FEMALE else "Cinnabar", "boots": "Umber",
			"accessories": ["ribbon"] if gender == FEMALE else ["sword"], "height": 1.0}, true)
	# keep the robe and inner layer from being the same colour
	if look["inner"] == look["robe"]:
		look["inner"] = "Moon White" if look["robe"] != "Moon White" else "Ink"
	return look

func slot_color(slot: String, look: Dictionary) -> Color:
	match slot:
		"robe", "inner", "sash":
			return ROBE_COLORS.get(look.get(slot, ""), Color.WHITE)
		"hair":
			return HAIR_COLORS.get(look.get("hair_color", ""), Color.WHITE)
		"skin":
			return SKIN_TONES.get(look.get("skin", ""), Color.WHITE)
		"boots":
			return BOOT_COLORS.get(look.get("boots", ""), Color.WHITE)
	return Color.WHITE

## Shows the chosen hair/accessories and tints material slots on `root`
## (an instanced cultivator_*.glb / npc_*.glb scene).
func apply(root: Node3D, look: Dictionary) -> void:
	var accs: Array = look.get("accessories", [])
	var h: float = look.get("height", 1.0)
	root.scale = Vector3(h, h, h)
	for mi in _meshes(root):
		var n := String(mi.name)
		if n.begins_with("hair_"):
			mi.visible = n == "hair_" + String(look.get("hair", ""))
		elif n.begins_with("acc_"):
			mi.visible = accs.has(n.substr(4))
		if not mi.visible or mi.mesh == null:
			continue
		for s in range(mi.mesh.get_surface_count()):
			var base := mi.mesh.surface_get_material(s) as BaseMaterial3D
			if base == null:
				continue
			var slot := base.resource_name.trim_prefix("M_")
			if slot in ["robe", "inner", "sash", "hair", "skin", "boots"]:
				mi.set_surface_override_material(s, _tinted(base, slot_color(slot, look)))
			else:
				mi.set_surface_override_material(s, null)

func _tinted(base: BaseMaterial3D, color: Color) -> Material:
	var key := "%d|%s" % [base.get_instance_id(), color.to_html()]
	if not _mat_cache.has(key):
		var m := base.duplicate() as BaseMaterial3D
		m.albedo_color = color
		_mat_cache[key] = m
	return _mat_cache[key]

func _meshes(node: Node, out: Array[MeshInstance3D] = []) -> Array[MeshInstance3D]:
	if node is MeshInstance3D:
		out.append(node)
	for c in node.get_children():
		_meshes(c, out)
	return out
