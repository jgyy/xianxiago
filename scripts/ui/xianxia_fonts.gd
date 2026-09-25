extends RefCounted
## Font helper for the Xianxia UI theme (assets/ui/xianxia_theme.tres).
##
## The theme ships without hard font references so it never fails to load:
## `apply(theme)` plugs in the brush-calligraphy font (Ma Shan Zheng) and a
## readable serif at runtime. Bundled OFL fonts under assets/fonts/ are used
## when present; otherwise it falls back to installed system fonts with
## CJK coverage, so Chinese glyphs never render as tofu.
##
## Usage from any UI script:
##   const XianxiaFonts := preload("res://scripts/ui/xianxia_fonts.gd")
##   XianxiaFonts.apply(theme)          # once; the Theme resource is shared

const THEME_PATH := "res://assets/ui/xianxia_theme.tres"

const BRUSH_FILES := [
	"res://assets/fonts/MaShanZheng-Regular.ttf",
	"res://assets/fonts/ZhiMangXing-Regular.ttf",
	"res://assets/fonts/LiuJianMaoCao-Regular.ttf",
]
const SERIF_FILES := [
	"res://assets/fonts/CormorantGaramond-Variable.ttf",
	"res://assets/fonts/CormorantGaramond-SemiBold.ttf",
	"res://assets/fonts/CormorantGaramond-Medium.ttf",
	"res://assets/fonts/CormorantGaramond-Regular.ttf",
	"res://assets/fonts/NotoSerifSC-Variable.ttf",
]
const BRUSH_SYSTEM := [
	"Ma Shan Zheng", "Zhi Mang Xing", "Liu Jian Mao Cao", "KaiTi", "STKaiti",
	"Kaiti SC", "AR PL UKai CN", "Noto Serif CJK SC", "Source Han Serif SC",
	"WenQuanYi Zen Hei", "Noto Sans CJK SC", "Microsoft YaHei", "serif",
]
const SERIF_SYSTEM := [
	"Cormorant Garamond", "EB Garamond", "Noto Serif", "Georgia",
	"Liberation Serif", "DejaVu Serif", "Times New Roman", "serif",
]

## Theme type variations that use the brush font (all others use the serif).
const BRUSH_TYPES := ["BrushLabel", "BrushTitle", "SealGlyph", "DialGlyph", "InkBrushLabel"]

static var _brush: Font
static var _serif: Font

static func brush() -> Font:
	if _brush == null:
		var plain_serif := _load_first(SERIF_FILES, SERIF_SYSTEM, [])
		_brush = _load_first(BRUSH_FILES, BRUSH_SYSTEM, [plain_serif])
	return _brush

static func serif() -> Font:
	if _serif == null:
		_serif = _load_first(SERIF_FILES, SERIF_SYSTEM, [brush()])
	return _serif

## True when the bundled calligraphy font file is available.
static func has_bundled_brush() -> bool:
	for path in BRUSH_FILES:
		if ResourceLoader.exists(path):
			return true
	return false

## Installs the fonts into `theme` (defaults to the shared Xianxia theme).
## Safe to call repeatedly.
static func apply(theme: Theme = null) -> Theme:
	if theme == null:
		theme = load(THEME_PATH) as Theme
	if theme == null:
		return null
	if theme.has_meta("xianxia_fonts_applied"):
		return theme
	theme.default_font = serif()
	for type_name in BRUSH_TYPES:
		theme.set_font("font", type_name, brush())
	theme.set_meta("xianxia_fonts_applied", true)
	return theme

static func _load_first(files: Array, system_names: Array, fallbacks: Array) -> Font:
	for path in files:
		if ResourceLoader.exists(path):
			var f := load(path) as FontFile
			if f != null:
				if f.fallbacks.is_empty():
					f.fallbacks = fallbacks
				return f
	var sf := SystemFont.new()
	sf.font_names = PackedStringArray(system_names)
	sf.fallbacks = fallbacks
	return sf
