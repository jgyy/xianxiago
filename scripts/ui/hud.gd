extends CanvasLayer

@onready var qi_bar: ProgressBar = %QiBar
@onready var qi_label: Label = %QiLabel
@onready var realm_label: Label = %RealmLabel
@onready var time_label: Label = %TimeLabel

func _ready() -> void:
	QiSystem.qi_changed.connect(_on_qi_changed)
	GameState.realm_changed.connect(_on_realm_changed)
	_on_qi_changed(QiSystem.current_qi, QiSystem.max_qi)
	_on_realm_changed(GameState.realm)

func _process(_delta: float) -> void:
	var t := WorldClock.time_of_day
	var hour := int(t)
	var minute := int((t - hour) * 60.0)
	time_label.text = "%02d:%02d" % [hour, minute]

func _on_qi_changed(current: float, max_qi: float) -> void:
	qi_bar.max_value = max_qi
	qi_bar.value = current
	qi_label.text = "Qi %d / %d" % [int(current), int(max_qi)]

func _on_realm_changed(_new_realm) -> void:
	realm_label.text = GameState.realm_name()
