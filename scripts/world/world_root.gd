extends Node3D
## Wires the player into the terrain streamer and drops them on the
## ground at spawn instead of at a hardcoded height.

@onready var streamer: WorldStreamer = $WorldStreamer
@onready var player: CharacterBody3D = $Player

func _ready() -> void:
	streamer.set_target(player)
	var ground_height := streamer.height_at(player.global_position.x, player.global_position.z)
	player.global_position.y = ground_height + 2.0
