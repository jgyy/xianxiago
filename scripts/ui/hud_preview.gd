extends Node
## Standalone HUD preview: the HUD over a still background, no 3D world.
## Handy for iterating on UI art and for screenshots:
##
##   godot --path . --resolution 1280x720 scenes/ui/HUDPreview.tscn -- \
##       --shot=/tmp/hud.png --time=9.5 --qi=0.68 --toast="Azure Cloud Town"
##
## Keys: T toast, R advance realm, Q spend qi, F1 key hints.

@export var background_path := "res://docs/screenshots/mountains.png"
@export var background_crop_top := 125 ## hides the old HUD baked into the shot

@onready var hud = $HUD
@onready var background: TextureRect = $Background

var _args := {}

func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var parts := a.trim_prefix("--").split("=", true, 1)
		_args[parts[0]] = parts[1] if parts.size() > 1 else ""
	_load_background(_args.get("bg", background_path))
	WorldClock.day_length_seconds = 1.0e9 # freeze the clock
	WorldClock.time_of_day = float(_args.get("time", "9.5"))
	var realm := int(_args.get("realm", "0"))
	for i in realm:
		GameState.advance_realm()
	QiSystem.regen_rate = 0.0
	var qi := float(_args.get("qi", "0.68"))
	QiSystem.try_spend(QiSystem.max_qi * (1.0 - qi))
	var text: String = _args.get("toast", "Azure Cloud Town")
	if not text.is_empty():
		get_tree().create_timer(0.3).timeout.connect(func(): hud.toast(text, 30.0))
	if _args.has("shot"):
		await get_tree().create_timer(float(_args.get("delay", "2.0"))).timeout
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		img.save_png(_args["shot"])
		print("HUD preview saved to ", _args["shot"])
		get_tree().quit()

func _load_background(path: String) -> void:
	var abs_path := ProjectSettings.globalize_path(path)
	var img := Image.load_from_file(abs_path) if FileAccess.file_exists(path) else null
	if img == null:
		return
	var top := clampi(background_crop_top, 0, img.get_height() - 1)
	img = img.get_region(Rect2i(0, top, img.get_width(), img.get_height() - top))
	background.texture = ImageTexture.create_from_image(img)

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match (event as InputEventKey).keycode:
		KEY_T:
			hud.toast("Azure Cloud Town")
		KEY_R:
			GameState.advance_realm()
		KEY_Q:
			QiSystem.try_spend(minf(25.0, QiSystem.current_qi))
