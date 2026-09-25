extends Node
## Autoload: tracks the player's cultivation progress.
## Xianxia cultivation realms, lowest to highest. Each realm raises the
## player's max qi pool (see QiSystem) and unlocks techniques later on.

enum Realm {
	MORTAL,
	QI_CONDENSATION,
	FOUNDATION_ESTABLISHMENT,
	CORE_FORMATION,
	NASCENT_SOUL,
}

const REALM_NAMES := {
	Realm.MORTAL: "Mortal",
	Realm.QI_CONDENSATION: "Qi Condensation",
	Realm.FOUNDATION_ESTABLISHMENT: "Foundation Establishment",
	Realm.CORE_FORMATION: "Core Formation",
	Realm.NASCENT_SOUL: "Nascent Soul",
}

## Max qi granted at each realm; QiSystem reads this on realm change.
const REALM_MAX_QI := {
	Realm.MORTAL: 100.0,
	Realm.QI_CONDENSATION: 160.0,
	Realm.FOUNDATION_ESTABLISHMENT: 240.0,
	Realm.CORE_FORMATION: 340.0,
	Realm.NASCENT_SOUL: 460.0,
}

signal realm_changed(new_realm: Realm)

var realm: Realm = Realm.MORTAL

## Which cultivator model the player uses (0 = male, 1 = female).
var body_type: int = 0
## Last customisation look per gender (see CharacterLooks), keyed by body_type.
var looks: Dictionary = {}

func realm_name() -> String:
	return REALM_NAMES.get(realm, "Unknown")

func max_qi_for_realm() -> float:
	return REALM_MAX_QI.get(realm, 100.0)

func advance_realm() -> void:
	if realm == Realm.NASCENT_SOUL:
		return
	realm = (realm + 1) as Realm
	realm_changed.emit(realm)
