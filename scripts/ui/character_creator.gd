extends CanvasLayer
## In-game cultivator customiser (V). Choose male/female, browse the 100
## named presets per gender, then fine-tune hair style and colour, skin,
## robe / inner / sash / boot colours, accessories and height. Changes apply
## live to the player through `player.set_look()`.

const THEME_PATH := "res://assets/ui/xianxia_theme.tres"

@export var player_path: NodePath = ^"../Player"

var _player: Node
var _look: Dictionary = {}
var _panel: PanelContainer
var _rows: Dictionary = {} # key -> value Label
var _preset_label: Label
var _acc_box: HBoxContainer
var _height: HSlider
var _building := false

func _ready() -> void:
	layer = 20
	_player = get_node_or_null(player_path)
	_build_ui()
	_panel.visible = false

func _unhandled_input(event: InputEvent) -> void:
	if InputMap.has_action("customize_character") and event.is_action_pressed("customize_character"):
		toggle()
		get_viewport().set_input_as_handled()

func toggle() -> void:
	_panel.visible = not _panel.visible
	if _panel.visible:
		_look = (_player.look as Dictionary).duplicate(true) if _player else CharacterLooks.preset(0, 0)
		_refresh()
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	else:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if has_node("/root/AudioManager"):
		get_node("/root/AudioManager").call("play_sfx", "ui_open_scroll" if _panel.visible else "ui_close_scroll")

func _build_ui() -> void:
	_panel = PanelContainer.new()
	if ResourceLoader.exists(THEME_PATH):
		_panel.theme = load(THEME_PATH)
	_panel.anchor_left = 1.0
	_panel.anchor_right = 1.0
	_panel.anchor_top = 0.5
	_panel.anchor_bottom = 0.5
	_panel.offset_left = -430
	_panel.offset_right = -24
	_panel.offset_top = -300
	_panel.offset_bottom = 300
	add_child(_panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	_panel.add_child(box)

	var title := Label.new()
	title.text = "Cultivator's Mirror"
	title.add_theme_font_size_override("font_size", 26)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)

	var genders := HBoxContainer.new()
	genders.alignment = BoxContainer.ALIGNMENT_CENTER
	for g in [["Male", 0], ["Female", 1]]:
		var b := Button.new()
		b.text = g[0]
		b.custom_minimum_size = Vector2(120, 32)
		b.pressed.connect(_set_gender.bind(g[1]))
		genders.add_child(b)
	box.add_child(genders)

	var preset := HBoxContainer.new()
	var prev := Button.new()
	prev.text = "<"
	prev.pressed.connect(_step_preset.bind(-1))
	var next := Button.new()
	next.text = ">"
	next.pressed.connect(_step_preset.bind(1))
	_preset_label = Label.new()
	_preset_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_preset_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	preset.add_child(prev)
	preset.add_child(_preset_label)
	preset.add_child(next)
	box.add_child(preset)
	box.add_child(HSeparator.new())

	for row in [["Hair style", "hair"], ["Hair colour", "hair_color"], ["Skin", "skin"], ["Robe", "robe"],
			["Inner robe", "inner"], ["Sash", "sash"], ["Boots", "boots"]]:
		box.add_child(_cycler(row[0], row[1]))

	var acc_title := Label.new()
	acc_title.text = "Adornments"
	box.add_child(acc_title)
	_acc_box = HBoxContainer.new()
	box.add_child(_acc_box)

	var hrow := HBoxContainer.new()
	var hl := Label.new()
	hl.text = "Height"
	hl.custom_minimum_size.x = 110
	_height = HSlider.new()
	_height.min_value = 0.9
	_height.max_value = 1.1
	_height.step = 0.01
	_height.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_height.value_changed.connect(func(v: float) -> void:
		if not _building:
			_look["height"] = v
			_push())
	hrow.add_child(hl)
	hrow.add_child(_height)
	box.add_child(hrow)

	var buttons := HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	var rnd := Button.new()
	rnd.text = "Fate's Choice"
	rnd.pressed.connect(func() -> void:
		_look = CharacterLooks.preset(_look.get("gender", 0), randi() % CharacterLooks.PRESET_COUNT)
		_refresh()
		_push())
	var done := Button.new()
	done.text = "Done (V)"
	done.pressed.connect(toggle)
	buttons.add_child(rnd)
	buttons.add_child(done)
	box.add_child(buttons)

func _cycler(label: String, key: String) -> Control:
	var row := HBoxContainer.new()
	var l := Label.new()
	l.text = label
	l.custom_minimum_size.x = 110
	var prev := Button.new()
	prev.text = "<"
	prev.pressed.connect(_cycle.bind(key, -1))
	var value := Label.new()
	value.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	value.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var next := Button.new()
	next.text = ">"
	next.pressed.connect(_cycle.bind(key, 1))
	row.add_child(l)
	row.add_child(prev)
	row.add_child(value)
	row.add_child(next)
	_rows[key] = value
	return row

func _options(key: String) -> Array:
	var g: int = _look.get("gender", 0)
	match key:
		"hair":
			return CharacterLooks.HAIR_STYLES[g]
		"hair_color":
			return CharacterLooks.HAIR_COLORS.keys()
		"skin":
			return CharacterLooks.SKIN_TONES.keys()
		"boots":
			return CharacterLooks.BOOT_COLORS.keys()
	return CharacterLooks.ROBE_COLORS.keys()

func _cycle(key: String, dir: int) -> void:
	var opts := _options(key)
	var i := opts.find(_look.get(key, opts[0]))
	_look[key] = opts[posmod(i + dir, opts.size())]
	_look["name"] = "Custom"
	_refresh()
	_push()

func _set_gender(g: int) -> void:
	var saved: Dictionary = GameState.looks.get(g, {})
	_look = saved.duplicate(true) if not saved.is_empty() else CharacterLooks.preset(g, 0)
	_refresh()
	_push()

func _step_preset(dir: int) -> void:
	_look = CharacterLooks.preset(_look.get("gender", 0), int(_look.get("index", 0)) + dir)
	_refresh()
	_push()

func _refresh() -> void:
	_building = true
	_preset_label.text = "%d / %d  ·  %s" % [int(_look.get("index", 0)) + 1, CharacterLooks.PRESET_COUNT, _look.get("name", "")]
	for key in _rows.keys():
		var v := String(_look.get(key, ""))
		(_rows[key] as Label).text = v.replace("_", " ").capitalize() if key == "hair" else v
	for c in _acc_box.get_children():
		c.queue_free()
	var g: int = _look.get("gender", 0)
	for acc in CharacterLooks.ACCESSORIES[g]:
		var cb := CheckBox.new()
		cb.text = acc.capitalize()
		cb.button_pressed = (_look.get("accessories", []) as Array).has(acc)
		cb.toggled.connect(func(on: bool) -> void:
			var list: Array = _look.get("accessories", []).duplicate()
			if on and not list.has(acc):
				list.append(acc)
			elif not on:
				list.erase(acc)
			_look["accessories"] = list
			_push())
		_acc_box.add_child(cb)
	_height.value = _look.get("height", 1.0)
	_building = false

func _push() -> void:
	if _player and _player.has_method("set_look"):
		_player.set_look(_look.duplicate(true))
