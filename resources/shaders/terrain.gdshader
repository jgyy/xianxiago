shader_type spatial;
// Open-world terrain splatting. Every layer is a Blender-baked texture from
// assets/textures; layers are chosen per pixel from height, slope and a
// large-scale macro-variation map so the ground is never one flat colour.
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D grass_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D meadow_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D forest_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dirt_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dirt_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D cliff_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D cliff_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D snow_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D snow_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D macro_map : filter_linear_mipmap, repeat_enable;

uniform float tile_size = 5.0;          // metres per texture repeat
uniform float cliff_tile_size = 11.0;
uniform float macro_size = 260.0;
uniform float water_level = -2.6;
uniform float rock_height = 8.0;
uniform float snow_height = 19.0;

varying vec3 world_pos;
varying vec3 world_nrm;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_nrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

// Height-aware blend: the layer with the "taller" texture detail wins at
// the transition so edges look like grass tufts / rock tops, not a smear.
float hblend(float base_mask, float detail, float sharp) {
	return clamp((base_mask - 0.5) * sharp + detail * 0.8 - 0.4 + 0.5, 0.0, 1.0);
}

vec3 unpack_n(vec4 t) {
	vec3 n = t.xyz * 2.0 - 1.0;
	return n;
}

void fragment() {
	vec2 uv = world_pos.xz / tile_size;
	// Two rotated/scaled lookups of the same map break up visible tiling.
	vec2 uv2 = mat2(vec2(0.8, -0.6), vec2(0.6, 0.8)) * uv * 0.37 + vec2(0.31, 0.17);
	vec3 macro = texture(macro_map, world_pos.xz / macro_size).rgb;
	vec3 macro2 = texture(macro_map, world_pos.xz / (macro_size * 0.23) + 0.5).rgb;

	float slope = 1.0 - clamp(world_nrm.y, 0.0, 1.0);
	float h = world_pos.y + (macro2.r - 0.5) * 3.0;

	// --- lowland greens: lush grass / flower meadow / forest floor
	vec3 grass = mix(texture(grass_albedo, uv).rgb, texture(grass_albedo, uv2).rgb, 0.35);
	vec3 meadow = texture(meadow_albedo, uv * 0.8).rgb;
	vec3 forest = texture(forest_albedo, uv * 1.2).rgb;
	float meadow_m = smoothstep(0.52, 0.66, macro.g);
	float forest_m = smoothstep(0.58, 0.72, macro.b) * (1.0 - meadow_m);
	vec3 col = mix(grass, meadow, meadow_m);
	col = mix(col, forest, forest_m);
	// warm/cool tint drift across kilometres so fields read as varied
	col *= mix(vec3(1.06, 1.02, 0.86), vec3(0.88, 1.02, 1.0), macro.r);
	vec3 nrm = unpack_n(texture(grass_normal, uv));

	// --- dirt paths / bare patches
	vec3 dirt = texture(dirt_albedo, uv * 0.9).rgb;
	float dirt_m = hblend(smoothstep(0.64, 0.74, macro2.g) + slope * 0.9, dot(dirt, vec3(0.33)), 3.0);
	col = mix(col, dirt, dirt_m);
	nrm = mix(nrm, unpack_n(texture(dirt_normal, uv * 0.9)), dirt_m);

	// --- sandy shore near the water line
	vec3 sand = texture(sand_albedo, uv * 1.3).rgb;
	float sand_m = 1.0 - smoothstep(water_level + 0.4, water_level + 1.6, h);
	col = mix(col, sand, sand_m);

	// --- rock on uplands and moderate slopes
	vec3 rock = texture(rock_albedo, uv * 0.6).rgb;
	float rock_m = max(smoothstep(rock_height - 1.5, rock_height + 1.5, h), smoothstep(0.22, 0.38, slope));
	rock_m = hblend(rock_m, dot(rock, vec3(0.33)), 4.0);
	col = mix(col, rock, rock_m);
	nrm = mix(nrm, unpack_n(texture(rock_normal, uv * 0.6)), rock_m);

	// --- layered cliffs on steep faces, triplanar so strata don't stretch
	vec3 bw = pow(abs(world_nrm), vec3(4.0));
	bw /= (bw.x + bw.y + bw.z);
	vec3 cx = texture(cliff_albedo, world_pos.zy / cliff_tile_size).rgb;
	vec3 cz = texture(cliff_albedo, world_pos.xy / cliff_tile_size).rgb;
	vec3 cy = texture(cliff_albedo, world_pos.xz / cliff_tile_size).rgb;
	vec3 cliff = cx * bw.x + cy * bw.y + cz * bw.z;
	float cliff_m = max(smoothstep(0.42, 0.58, slope), smoothstep(0.22, 0.4, slope) * smoothstep(rock_height, rock_height + 6.0, h));
	col = mix(col, cliff, cliff_m);
	nrm = mix(nrm, unpack_n(texture(cliff_normal, world_pos.xz / cliff_tile_size)), cliff_m);

	// --- snow caps on high, gentle ground
	vec3 snow = texture(snow_albedo, uv * 0.7).rgb * mix(vec3(0.86, 0.9, 0.98), vec3(0.95), macro2.b);
	float snow_m = smoothstep(snow_height - 1.0, snow_height + 2.5, h + (macro.g - 0.5) * 6.0) * (1.0 - smoothstep(0.28, 0.42, slope));
	snow_m = hblend(snow_m, 1.0 - dot(col, vec3(0.33)), 3.0);
	col = mix(col, snow, snow_m);
	nrm = mix(nrm, unpack_n(texture(snow_normal, uv * 0.7)), snow_m);

	ALBEDO = col;
	NORMAL_MAP = normalize(nrm) * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = 1.2;
	ROUGHNESS = mix(0.92, 0.55, snow_m) - sand_m * 0.1;
	SPECULAR = 0.35;
}
