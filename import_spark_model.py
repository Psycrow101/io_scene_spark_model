import bpy

from bpy_extras import node_shader_utils
from bpy_extras.image_utils import load_image
from os import path

from . spark_model import *

POSEDATA_PREFIX = 'pose.bones["%s"].'


def invalid_model_format(self, context):
    self.layout.label(text='Invalid model format')


def invalid_animation_model(self, context):
    self.layout.label(text='Invalid external animation model')


def set_keyframe(curves, frame, values):
    for i, c in enumerate(curves):
        c.keyframe_points.add(1)
        c.keyframe_points[-1].co = frame, values[i]
        c.keyframe_points[-1].interpolation = 'LINEAR'


def create_actions(context, arm_obj, chunks):
    chunk_bones = chunks.get(ChunkBones)
    chunk_animations = chunks.get(ChunkAnimations)
    chunk_animation_nodes = chunks.get(ChunkAnimationNodes)
    chunk_sequences = chunks.get(ChunkSequences)
    chunk_blend_parameters = chunks.get(ChunkBlendParameters)

    if not chunk_animations:
        return

    animation_data = arm_obj.animation_data
    if not animation_data:
        animation_data = arm_obj.animation_data_create()

    context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    actions = []

    for a in chunk_animations.animations:
        act = bpy.data.actions.new('action')

        curves_loc, curves_rot, curves_scale = {}, {}, {}
        for b in a.keys:
            bone_name = chunk_bones.bones[b].name
            g = act.groups.new(name=bone_name)
            cl = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone_name) + 'location', index=i) for i in range(3)]
            cr = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone_name) + 'rotation_quaternion', index=i) for i in range(4)]
            cs = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone_name) + 'scale', index=i) for i in range(3)]

            for c in cl:
                c.group = g
            for c in cr:
                c.group = g
            for c in cs:
                c.group = g

            curves_loc[b] = cl
            curves_rot[b] = cr
            curves_scale[b] = cs

            arm_obj.pose.bones[bone_name].rotation_mode = 'QUATERNION'

        frames_num = len(list(a.keys.values())[0])
        for f in range(frames_num):
            for b, vals in a.keys.items():
                bone = arm_obj.pose.bones[chunk_bones.bones[b].name]

                mat = vals[f].to_mat4x4()
                if bone.parent:
                    mat = bone.parent.matrix @ mat
                bone.matrix = mat

                set_keyframe(curves_loc[b], f, bone.location)
                set_keyframe(curves_rot[b], f, bone.rotation_quaternion)
                set_keyframe(curves_scale[b], f, bone.scale)

        animation_data.action = act
        context.scene.frame_start = 0
        context.scene.frame_end = frames_num
        actions.append(act)

    bpy.ops.object.mode_set(mode='OBJECT')

    if not chunk_sequences:
        return

    for s in chunk_sequences.sequences:
        an = chunk_animation_nodes.animation_nodes[s.animation_node]
        if an.node_type == NodeType.ANIMATION:
            actions[an.data.animation].name = s.name
        elif an.node_type == NodeType.BLEND:
            pass
        else:
            pass


def create_cameras(collection, arm_obj, chunks):
    chunk_bones = chunks.get(ChunkBones)
    chunk_cameras = chunks.get(ChunkCameras)

    if not chunk_cameras:
        return

    for c in chunk_cameras.cameras:
        camera = bpy.data.cameras.new(name='camera')
        camera.angle_x = c.fov
        camera_obj = bpy.data.objects.new(c.name, camera)
        camera_obj.matrix_local = c.coords.to_mat4x4()
        camera_obj.parent = arm_obj
        constraint = camera_obj.constraints.new(type='CHILD_OF')
        constraint.target = arm_obj
        constraint.subtarget = chunk_bones.bones[c.bone].name
        collection.objects.link(camera_obj)


def create_attach_points(collection, arm_obj, chunks):
    chunk_bones = chunks.get(ChunkBones)
    chunk_attach_points = chunks.get(ChunkAttachPoints)

    if not chunk_attach_points:
        return

    for ap in chunk_attach_points.attach_points:
        point_obj = bpy.data.objects.new(ap.name, None)
        point_obj.empty_display_size = 0.1
        point_obj.matrix_local = ap.coords.to_mat4x4()
        point_obj.parent = arm_obj
        constraint = point_obj.constraints.new(type='CHILD_OF')
        constraint.target = arm_obj
        constraint.subtarget = chunk_bones.bones[ap.bone].name
        collection.objects.link(point_obj)


def create_iamge(img_path):
    img_name = path.basename(img_path)

    img = bpy.data.images.get(img_name)
    if img:
        return img

    if not path.exists(img_path):
        return None

    return load_image(img_path)


def create_materials(mesh, chunk_materials, game_directory):
    for mn in chunk_materials.material_names:
        mat_name = path.basename(mn)
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(name=mat_name)
            mat_path = path.join(game_directory, mn)

            if not path.exists(mat_path):
                continue

            mat_params = {}
            with open(mat_path, 'r') as fd:
                for line in fd:
                    splited = line.split('=')
                    if len(splited) != 2:
                        continue
                    key, val = map(lambda s: s.strip().replace('"', ''), splited)
                    mat_params[key] = val

            mat_wrap = node_shader_utils.PrincipledBSDFWrapper(mat, is_readonly=False)

            if 'albedoMap' in mat_params:
                img_path = path.join(game_directory, mat_params['albedoMap'])
                img = create_iamge(img_path)
                if img:
                    nodetex = mat_wrap.base_color_texture
                    nodetex.image = img
                    nodetex.texcoords = 'UV'

            if 'normalMap' in mat_params:
                img_path = path.join(game_directory, mat_params['normalMap'])
                img = create_iamge(img_path)
                if img:
                    mat_wrap.normalmap_texture.image = img

            if 'specularMap' in mat_params:
                img_path = path.join(game_directory, mat_params['specularMap'])
                img = create_iamge(img_path)
                if img:
                    mat_wrap.specular_texture.image = img

            if 'emissiveMap' in mat_params:
                img_path = path.join(game_directory, mat_params['emissiveMap'])
                img = create_iamge(img_path)
                if img:
                    mat_wrap.emission_color_texture.image = img

        mesh.materials.append(mat)


def read_all_chunks(fd):
    chunks = {}
    while True:
        try:
            chunk = read_chunk(fd)
            chunks[type(chunk)] = chunk
        except ErrorUnknownChunk as e:
            print(e) # TODO: remove
        except ErrorChunkEOF:
            break
    return chunks


def load(context, filepath, *, game_directory, import_actions, import_cameras, import_attach_points, global_matrix):
    view_layer = context.view_layer
    collection = view_layer.active_layer_collection.collection

    with open(filepath, 'rb') as fd:
        if fd.read(4) != b'MDL\x07':
            context.window_manager.popup_menu(invalid_model_format, title='Error', icon='ERROR')
            return {'CANCELLED'}
        chunks = read_all_chunks(fd)

    chunk_vertices = chunks.get(ChunkVertices)
    chunk_indices = chunks.get(ChunkIndices)
    chunk_face_sets = chunks.get(ChunkFaceSets)
    chunk_bones = chunks.get(ChunkBones)
    chunk_materials = chunks.get(ChunkMaterials)
    chunk_animation_model = chunks.get(ChunkAnimationModel)

    vertices = [v.co for v in chunk_vertices.vertices]
    faces = [i for i in chunk_indices.indices]
    normals = [v.nrm for v in chunk_vertices.vertices]
    uvs = [(v.uv[0], 1.0 - v.uv[1]) for v in chunk_vertices.vertices]

    mesh = bpy.data.meshes.new('mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.normals_split_custom_set_from_vertices(normals)
    mesh.use_auto_smooth = True

    create_materials(mesh, chunk_materials, game_directory)

    uv_layer = mesh.uv_layers.new()
    for f, face in enumerate(mesh.polygons):
        for i, loop in enumerate(face.loop_indices):
            uv_layer.data[loop].uv = uvs[faces[f][i]]

    arm = bpy.data.armatures.new('arm')
    arm_obj = bpy.data.objects.new(path.basename(filepath), arm)
    arm_obj.show_in_front = True
    arm_obj.matrix_world = global_matrix

    mesh_obj = bpy.data.objects.new('model', mesh)
    mesh_obj.parent = arm_obj
    modifier = mesh_obj.modifiers.new(type='ARMATURE', name='Armature')
    modifier.object = arm_obj

    vert2face = {}
    for i, fc in enumerate(chunk_face_sets.face_sets):
        for f in range(fc.first_face, fc.first_face + fc.faces_num):
            mesh.polygons[f].material_index = fc.mat_index
            vert2face[faces[f][0]] = i
            vert2face[faces[f][1]] = i
            vert2face[faces[f][2]] = i

    vert_groups = [mesh_obj.vertex_groups.new(name=b.name) for b in chunk_bones.bones]
    for i, v in enumerate(chunk_vertices.vertices):
        face = vert2face[i]
        bones = chunk_face_sets.face_sets[face].bones
        for weight, bone in zip(v.bone_weights[::2], v.bone_weights[1::2]):
            if weight > 0.0:
                vert_groups[bones[bone]].add([i], weight, 'REPLACE')

    collection.objects.link(mesh_obj)
    collection.objects.link(arm_obj)

    view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')

    bones = []
    for i, b in enumerate(chunk_bones.bones):
        bone = arm.edit_bones.new(b.name)
        bone.head = (0, 0, 0)
        bone.tail = (0, 0, 0.1)

        mat = b.affine_parts.to_mat4x4()
        if b.parent > -1:
            bone.parent = bones[b.parent]
            mat = bones[b.parent].matrix @ mat

        bone.matrix = mat
        bones.append(bone)

    bpy.ops.object.mode_set(mode='OBJECT')

    if import_actions:
        create_actions(context, arm_obj, chunks)

        if chunk_animation_model and path.exists(game_directory):
            success = False
            external_model_path = path.join(game_directory, chunk_animation_model.path)
            if path.exists(external_model_path):
                with open(external_model_path, 'rb') as fd:
                    if fd.read(4) == b'MDL\x07':
                        create_actions(context, arm_obj, read_all_chunks(fd))
                        success = True
            if not success:
                context.window_manager.popup_menu(invalid_animation_model, title='Warning', icon='ERROR')

    if import_cameras:
        create_cameras(collection, arm_obj, chunks)

    if import_attach_points:
        create_attach_points(collection, arm_obj, chunks)

    return {'FINISHED'}
