shader_type spatial;
// Lake surface: two scrolling copies of the Blender-baked ripple normal map,
// jade-tinted depth colour and a soft foam line where it meets the shore.
render_mode blend_mix, depth_draw_always, cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D ripple_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D foam_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D depth_tex : hint_depth_texture, filter_linear_mipmap;
uniform vec3 shallow_color : source_color = vec3(0.28, 0.62, 0.58);
uniform vec3 deep_color : source_color = vec3(0.05, 0.22, 0.30);
uniform float ripple_scale = 14.0;
uniform float flow_speed = 0.02;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = world_pos.xz / ripple_scale;
	vec3 n1 = texture(ripple_normal, uv + TIME * flow_speed * vec2(1.0, 0.4)).rgb;
	vec3 n2 = texture(ripple_normal, uv * 1.7 - TIME * flow_speed * vec2(0.3, 1.0)).rgb;
	NORMAL_MAP = normalize(n1 + n2 - 1.0) * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = 0.6;

	float scene_depth = texture(depth_tex, SCREEN_UV).r;
	vec4 world = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, scene_depth, 1.0);
	float lin = -world.z / world.w;
	float thickness = clamp(lin - (-VERTEX.z), 0.0, 20.0);
	float d = 1.0 - exp(-thickness * 0.35);
	ALBEDO = mix(shallow_color, deep_color, d);
	float foam = (1.0 - smoothstep(0.0, 0.9, thickness)) * texture(foam_tex, uv * 3.0 + TIME * 0.01).r;
	ALBEDO = mix(ALBEDO, vec3(0.95, 0.97, 0.95), clamp(foam * 1.5, 0.0, 1.0));
	ALPHA = clamp(0.55 + d * 0.4 + foam, 0.0, 0.96);
	ROUGHNESS = 0.06;
	METALLIC = 0.0;
	SPECULAR = 0.6;
}
