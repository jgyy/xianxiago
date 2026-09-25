class_name TerrainChunk
extends StaticBody3D
## One square tile of the open-world terrain. Heights come from the
## streamer's shared height function so neighbouring chunks line up
## seamlessly; normals are sampled from that same function (not per-chunk
## generate_normals) so lighting has no seams at chunk borders either.
## Surface look comes from the splatting shader in terrain_material.tres.

@onready var mesh_instance: MeshInstance3D = $MeshInstance3D
@onready var collision_shape: CollisionShape3D = $CollisionShape3D

func build(
	chunk_coord: Vector2i,
	chunk_size: float,
	resolution: int,
	height_fn: Callable,
	material: Material
) -> void:
	name = "Chunk_%d_%d" % [chunk_coord.x, chunk_coord.y]
	position = Vector3(chunk_coord.x * chunk_size, 0.0, chunk_coord.y * chunk_size)

	var mesh := _generate_mesh(chunk_coord, chunk_size, resolution, height_fn)
	mesh_instance.mesh = mesh
	mesh_instance.material_override = material

	collision_shape.shape = mesh.create_trimesh_shape()

func _generate_mesh(
	chunk_coord: Vector2i,
	chunk_size: float,
	resolution: int,
	height_fn: Callable
) -> ArrayMesh:
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var indices := PackedInt32Array()

	var step := chunk_size / float(resolution)
	var origin_x := chunk_coord.x * chunk_size
	var origin_z := chunk_coord.y * chunk_size
	var e := step * 0.5

	for z in range(resolution + 1):
		for x in range(resolution + 1):
			var world_x := origin_x + x * step
			var world_z := origin_z + z * step
			var h: float = height_fn.call(world_x, world_z)
			verts.append(Vector3(x * step, h, z * step))
			var dx: float = height_fn.call(world_x - e, world_z) - height_fn.call(world_x + e, world_z)
			var dz: float = height_fn.call(world_x, world_z - e) - height_fn.call(world_x, world_z + e)
			normals.append(Vector3(dx, 2.0 * e, dz).normalized())
			# world-space UVs so the shader's tangents line up with world X/Z
			uvs.append(Vector2(world_x, world_z) / 8.0)

	for z in range(resolution):
		for x in range(resolution):
			var i0 := z * (resolution + 1) + x
			var i1 := i0 + 1
			var i2 := i0 + (resolution + 1)
			var i3 := i2 + 1
			# Godot treats clockwise winding (seen from the camera) as the
			# front face. Viewed from above (+Y) that's i0 -> i1 -> i2, so
			# the top of the terrain isn't back-face culled and the trimesh
			# collider's solid side faces the player instead of letting them
			# sink through and wedge.
			indices.append(i0)
			indices.append(i1)
			indices.append(i2)
			indices.append(i1)
			indices.append(i3)
			indices.append(i2)

	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = indices

	var array_mesh := ArrayMesh.new()
	array_mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

	var surface_tool := SurfaceTool.new()
	surface_tool.create_from(array_mesh, 0)
	surface_tool.generate_tangents()
	return surface_tool.commit()
