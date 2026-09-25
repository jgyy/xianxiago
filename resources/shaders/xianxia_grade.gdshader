shader_type spatial;
// Full-screen "ink and jade" colour grade, drawn by a quad parented to the
// camera. It pulls greens toward jade, cools the shadows into indigo ink,
// warms the highlights toward pale gold, lays jade-white mist into the
// distance and valleys, and adds a soft ink-wash vignette with paper grain.
render_mode unshaded, depth_draw_never, depth_test_disabled, cull_disabled, skip_vertex_transform, fog_disabled;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D paper_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 mist_color : source_color = vec3(0.84, 0.90, 0.88);
uniform float mist_start = 60.0;
uniform float mist_end = 520.0;
uniform float mist_strength = 0.55;
uniform float mist_height = 14.0;     // valley mist lies below this world height
uniform vec3 shadow_tint : source_color = vec3(0.80, 0.88, 1.0);
uniform vec3 highlight_tint : source_color = vec3(1.04, 1.0, 0.90);
uniform float jade_shift = 0.35;      // 0 = untouched greens, 1 = full jade
uniform float saturation = 0.92;
uniform float vignette = 0.38;
uniform float grain = 0.035;

void vertex() {
	POSITION = vec4(VERTEX.xy * 2.0, 1.0, 1.0);
}

vec3 rgb2hsv(vec3 c) {
	vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
	vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
	vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
	float d = q.x - min(q.w, q.y);
	return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
}

vec3 hsv2rgb(vec3 c) {
	vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
	return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

void fragment() {
	vec3 col = textureLod(screen_tex, SCREEN_UV, 0.0).rgb;
	float depth = textureLod(depth_tex, SCREEN_UV, 0.0).r;
	vec4 view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
	view.xyz /= view.w;
	float dist = length(view.xyz);
	vec3 world = (INV_VIEW_MATRIX * vec4(view.xyz, 1.0)).xyz;
	bool is_sky = depth <= 0.00001;

	// greens -> jade: rotate yellow-greens toward blue-green and soften them
	vec3 hsv = rgb2hsv(col);
	float green = smoothstep(0.12, 0.22, hsv.x) * (1.0 - smoothstep(0.42, 0.52, hsv.x));
	hsv.x = mix(hsv.x, mix(hsv.x, 0.40, 0.55), green * jade_shift);
	hsv.y *= mix(1.0, 0.82, green * jade_shift);
	col = hsv2rgb(hsv);

	// split tone: ink-blue shadows, pale gold highlights
	float lum = dot(col, vec3(0.299, 0.587, 0.114));
	col *= mix(shadow_tint, highlight_tint, smoothstep(0.15, 0.75, lum));
	col = mix(vec3(lum), col, saturation);

	// layered mountain mist: distance + low-lying valley fog
	if (!is_sky) {
		float far_m = smoothstep(mist_start, mist_end, dist);
		float low_m = (1.0 - smoothstep(mist_height - 12.0, mist_height + 6.0, world.y)) * smoothstep(25.0, 220.0, dist);
		float m = clamp(max(far_m, low_m * 0.8) * mist_strength, 0.0, 0.85);
		col = mix(col, mist_color * max(lum * 0.4 + 0.75, 0.35) * mix(0.35, 1.0, clamp(lum * 3.0, 0.0, 1.0)), m);
	}

	// rice-paper grain and ink-wash vignette
	vec2 uv = SCREEN_UV;
	float paper = texture(paper_tex, uv * vec2(VIEWPORT_SIZE.x / VIEWPORT_SIZE.y, 1.0) * 2.2).r;
	col *= 1.0 + (paper - 0.5) * grain;
	float v = smoothstep(0.35, 1.05, length((uv - 0.5) * vec2(1.25, 1.0)) * 1.25);
	col = mix(col, col * vec3(0.55, 0.60, 0.66), v * vignette);
	ALBEDO = col;
}
