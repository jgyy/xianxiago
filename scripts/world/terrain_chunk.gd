class_name TerrainChunk
extends StaticBody3D
## One square tile of the open-world terrain. Built procedurally from a
## shared FastNoiseLite so neighboring chunks line up seamlessly, and
## colored per-vertex by height/slope so it reads as grass/rock/snow
## without needing any textures.

@onready var mesh_instance: MeshInstance3D = $MeshInstance3D
@onready var collision_shape: CollisionShape3D = $CollisionShape3D

const SNOW_HEIGHT := 9.0
const ROCK_HEIGHT := 4.5
const GRASS_COLOR := Color(0.20, 0.46, 0.28)
const ROCK_COLOR := Color(0.42, 0.39, 0.36)
const SNOW_COLOR := Color(0.92, 0.94, 0.97)

func build(
	chunk_coord: Vector2i,
	chunk_size: float,
	resolution: int,
	noise: FastNoiseLite,
	height_scale: float,
	material: Material
) -> void:
	name = "Chunk_%d_%d" % [chunk_coord.x, chunk_coord.y]
	position = Vector3(chunk_coord.x * chunk_size, 0.0, chunk_coord.y * chunk_size)

	var mesh := _generate_mesh(chunk_coord, chunk_size, resolution, noise, height_scale)
	mesh_instance.mesh = mesh
	mesh_instance.material_override = material

	collision_shape.shape = mesh.create_trimesh_shape()

func _generate_mesh(
	chunk_coord: Vector2i,
	chunk_size: float,
	resolution: int,
	noise: FastNoiseLite,
	height_scale: float
) -> ArrayMesh:
	var verts := PackedVector3Array()
	var uvs := PackedVector2Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()

	var step := chunk_size / float(resolution)
	var origin_x := chunk_coord.x * chunk_size
	var origin_z := chunk_coord.y * chunk_size

	for z in range(resolution + 1):
		for x in range(resolution + 1):
			var world_x := origin_x + x * step
			var world_z := origin_z + z * step
			var h := noise.get_noise_2d(world_x, world_z) * height_scale
			verts.append(Vector3(x * step, h, z * step))
			uvs.append(Vector2(float(x) / resolution, float(z) / resolution))
			colors.append(_height_color(h))

	for z in range(resolution):
		for x in range(resolution):
			var i0 := z * (resolution + 1) + x
			var i1 := i0 + 1
			var i2 := i0 + (resolution + 1)
			var i3 := i2 + 1
			indices.append(i0)
			indices.append(i2)
			indices.append(i1)
			indices.append(i1)
			indices.append(i2)
			indices.append(i3)

	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices

	var array_mesh := ArrayMesh.new()
	array_mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

	var surface_tool := SurfaceTool.new()
	surface_tool.create_from(array_mesh, 0)
	surface_tool.generate_normals()
	return surface_tool.commit()

func _height_color(h: float) -> Color:
	if h < ROCK_HEIGHT:
		return GRASS_COLOR.lerp(ROCK_COLOR, smoothstep(ROCK_HEIGHT - 2.0, ROCK_HEIGHT, h))
	return ROCK_COLOR.lerp(SNOW_COLOR, smoothstep(ROCK_HEIGHT, SNOW_HEIGHT, h))
