shader_type sky;
// Painted Xianxia sky: azure zenith grading into a warm, hazy horizon, two
// drifting cloud layers, layered mountain silhouettes on the horizon and a
// star field at night. Every texture is baked by tools/blender/gen_textures.py.
render_mode use_half_res_pass;

uniform sampler2D clouds_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D wisps_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D stars_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D mountains_far : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D mountains_near : source_color, filter_linear_mipmap, repeat_enable;

// Day palette
uniform vec3 day_zenith : source_color = vec3(0.30, 0.54, 0.72);
uniform vec3 day_mid : source_color = vec3(0.60, 0.78, 0.84);
uniform vec3 day_horizon : source_color = vec3(0.92, 0.92, 0.86);
// Dawn / dusk palette
uniform vec3 dusk_zenith : source_color = vec3(0.30, 0.30, 0.52);
uniform vec3 dusk_mid : source_color = vec3(0.88, 0.62, 0.62);
uniform vec3 dusk_horizon : source_color = vec3(1.0, 0.78, 0.52);
// Night palette
uniform vec3 night_zenith : source_color = vec3(0.05, 0.09, 0.22);
uniform vec3 night_mid : source_color = vec3(0.10, 0.16, 0.34);
uniform vec3 night_horizon : source_color = vec3(0.20, 0.27, 0.45);
// Mist that fills the valleys below the horizon line
uniform vec3 mist_day : source_color = vec3(0.84, 0.90, 0.88);
uniform vec3 mist_night : source_color = vec3(0.17, 0.22, 0.36);

uniform vec3 sun_dir = vec3(0.0, 0.7, -0.7); // set by sun_light.gd
uniform float cloud_speed = 0.004;
uniform float cloud_coverage = 0.5;
uniform float exposure = 1.0;

vec3 sky_gradient(float el, vec3 z, vec3 m, vec3 h) {
	float t = clamp(el, 0.0, 1.0);
	vec3 low = mix(h, m, smoothstep(0.0, 0.22, t));
	return mix(low, z, smoothstep(0.18, 0.85, t));
}

void sky() {
	vec3 dir = EYEDIR;
	vec3 sdir = normalize(sun_dir);
	float sun_el = sdir.y;
	float day = smoothstep(-0.12, 0.25, sun_el);
	float dusk = (1.0 - smoothstep(0.05, 0.4, abs(sun_el + 0.02))) ;
	float night = 1.0 - smoothstep(-0.25, 0.02, sun_el);

	float el = dir.y;
	vec3 z = mix(mix(night_zenith, dusk_zenith, 1.0 - night), day_zenith, day * (1.0 - dusk * 0.6));
	vec3 m = mix(mix(night_mid, dusk_mid, 1.0 - night), day_mid, day * (1.0 - dusk * 0.7));
	vec3 hz = mix(mix(night_horizon, dusk_horizon, 1.0 - night), day_horizon, day * (1.0 - dusk * 0.8));
	// dusk colours concentrate on the sun's side of the sky
	float sun_side = pow(max(dot(normalize(dir.xz + 1e-4), normalize(sdir.xz + 1e-4)), 0.0), 2.0);
	hz = mix(hz, mix(hz, dusk_horizon * 1.1, 0.6), dusk * sun_side);
	vec3 col = sky_gradient(max(el, 0.0), z, m, hz);

	// sun disc + halo
	float sd = dot(dir, sdir);
	vec3 sun_col = mix(vec3(1.0, 0.55, 0.3), vec3(1.0, 0.95, 0.85), day);
	col += sun_col * (pow(max(sd, 0.0), 700.0) * 18.0 + pow(max(sd, 0.0), 12.0) * 0.35 * (0.4 + dusk)) * (1.0 - night);
	// moon opposite the sun
	float md = dot(dir, -sdir);
	col += vec3(0.75, 0.82, 1.0) * (smoothstep(0.9993, 0.9996, md) * 1.6 + pow(max(md, 0.0), 60.0) * 0.15) * night;

	if (!AT_CUBEMAP_PASS) {
		// stars
		if (el > 0.0) {
			vec2 suv = dir.xz / (el + 0.35) * 1.6;
			vec3 stars = texture(stars_tex, suv).rgb;
			col += stars * night * smoothstep(0.0, 0.25, el) * 1.4;
		}
		// two cloud decks projected on a dome
		if (el > -0.02) {
			vec2 cuv = dir.xz / (max(el, 0.0) + 0.12);
			float d1 = texture(clouds_tex, cuv * 0.22 + TIME * cloud_speed * vec2(1.0, 0.3)).r;
			float d2 = texture(wisps_tex, cuv * 0.12 + TIME * cloud_speed * vec2(0.6, -0.2)).r;
			float cov = smoothstep(1.0 - cloud_coverage, 1.0, d1 * 0.85 + 0.25) ;
			float wisp = d2 * 0.55;
			float fade = smoothstep(-0.02, 0.12, el) * (1.0 - smoothstep(0.75, 1.0, el) * 0.5);
			vec3 lit = mix(vec3(0.18, 0.2, 0.3), mix(vec3(1.0, 0.72, 0.62), vec3(1.0, 0.99, 0.96), day * (1.0 - dusk * 0.7)), 1.0 - night * 0.85);
			vec3 shade = mix(lit * 0.55, hz, 0.35);
			float silver = pow(max(sd, 0.0), 6.0) * (1.0 - night);
			vec3 cc = mix(shade, lit, clamp(d1 * 1.4 - 0.2, 0.0, 1.0)) + sun_col * silver * 0.5;
			col = mix(col, cc, clamp(cov * 0.95 + wisp * (1.0 - cov), 0.0, 0.95) * fade);
		}
		// horizon mountain ranges (panorama around the viewer)
		float u = atan(dir.x, dir.z) / TAU + 0.5;
		vec3 haze = mix(mist_night, mix(hz, mist_day, 0.5), 1.0 - night);
		float vfar = el / 0.16;
		if (vfar > -0.05 && vfar < 1.0) {
			vec4 mf = texture(mountains_far, vec2(u * 2.0, 1.0 - clamp(vfar, 0.0, 1.0)));
			vec3 mc = mix(mf.rgb * mix(0.25, 1.0, 1.0 - night), haze, 0.55);
			col = mix(col, mc, mf.a);
		}
		float vnear = (el + 0.01) / 0.1;
		if (vnear > -0.05 && vnear < 1.0) {
			vec4 mn = texture(mountains_near, vec2(u * 3.0 + 0.37, 1.0 - clamp(vnear, 0.0, 1.0)));
			vec3 mc = mix(mn.rgb * mix(0.2, 1.0, 1.0 - night), haze, 0.35);
			col = mix(col, mc, mn.a);
		}
		// valley mist below the horizon
		if (el < 0.0) {
			col = mix(col, haze, smoothstep(0.0, -0.08, el));
		}
	} else if (el < 0.0) {
		col = mix(col, mix(mist_night, mist_day, 1.0 - night), smoothstep(0.0, -0.1, el));
	}
	COLOR = col * exposure;
}
