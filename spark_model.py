from enum import Enum
from mathutils import Matrix, Quaternion
from os import SEEK_CUR
from struct import unpack


def read_string(fd):
    length = unpack('<I', fd.read(4))[0]
    return fd.read(length).decode()


def read_chunk(fd):
    header = fd.read(8)
    if header == b'':
        raise ErrorChunkEOF
    chunk_id, length = unpack('<2I', header)
    chunk_cls = id_to_chunk_cls(chunk_id)
    if not chunk_cls:
        fd.seek(length, SEEK_CUR)
        raise ErrorUnknownChunk(chunk_id)

    chunk = chunk_cls()
    chunk.read_data(fd)
    return chunk


def id_to_chunk_cls(chunk_id):
    chunks = {
        1: ChunkVertices,
        2: ChunkIndices,
        3: ChunkFaceSets,
        4: ChunkMaterials,
        6: ChunkBones,
        7: ChunkAnimations,
        8: ChunkAnimationNodes,
        9: ChunkSequences,
        10: ChunkBlendParameters,
        11: ChunkCameras,
        13: ChunkAttachPoints,
        19: ChunkAnimationModel,
    }
    return chunks.get(chunk_id)


class ErrorChunkEOF(Exception):
    pass


class ErrorUnknownChunk(Exception):
    def __init__(self, chunk_id):
        self.chunk_id = chunk_id

    def __str__(self):
        return 'Unknown chunk id: %d' % self.chunk_id


class ChunkVertices:
    def read_data(self, fd):
        vertices_num = unpack('<I', fd.read(4))[0]
        self.vertices = [Vertex.read(fd) for _ in range(vertices_num)]


class ChunkIndices:
    def read_data(self, fd):
        indices_num = unpack('<I', fd.read(4))[0]
        self.indices = [unpack('<3I', fd.read(12)) for _ in range(indices_num // 3)]


class ChunkFaceSets:
    def read_data(self, fd):
        face_sets_num = unpack('<I', fd.read(4))[0]
        self.face_sets = [FaceSet.read(fd) for _ in range(face_sets_num)]


class ChunkMaterials:
    def read_data(self, fd):
        materials_num = unpack('<I', fd.read(4))[0]
        self.material_names = [read_string(fd) for _ in range(materials_num)]


class ChunkBones:
    def read_data(self, fd):
        bones_num = unpack('<I', fd.read(4))[0]
        self.bones = [Bone.read(fd) for _ in range(bones_num)]


class ChunkAnimations:
    def read_data(self, fd):
        animations_num = unpack('<I', fd.read(4))[0]
        self.animations = [Animation.read(fd) for _ in range(animations_num)]


class ChunkAnimationNodes:
    def read_data(self, fd):
        animation_nodes_num = unpack('<I', fd.read(4))[0]
        self.animation_nodes = [AnimationNode.read(fd) for _ in range(animation_nodes_num)]


class ChunkSequences:
    def read_data(self, fd):
        sequences_num = unpack('<I', fd.read(4))[0]
        self.sequences = [Sequence.read(fd) for _ in range(sequences_num)]


class ChunkBlendParameters:
    def read_data(self, fd):
        blend_parameters_num = unpack('<I', fd.read(4))[0]
        self.blend_names = [read_string(fd) for _ in range(blend_parameters_num)]


class ChunkCameras:
    def read_data(self, fd):
        cameras_num = unpack('<I', fd.read(4))[0]
        self.cameras = [Camera.read(fd) for _ in range(cameras_num)]


class ChunkAttachPoints:
    def read_data(self, fd):
        attach_points_num = unpack('<I', fd.read(4))[0]
        self.attach_points = [AttachPoint.read(fd) for _ in range(attach_points_num)]


class ChunkAnimationModel:
    def read_data(self, fd):
        self.path = read_string(fd)


class NodeType(Enum):
    ANIMATION = 1
    BLEND = 2
    LAYER = 3


class Coords:
    def __init__(self, x_axis, y_axis, z_axis, origin):
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.z_axis = z_axis
        self.origin = origin

    @classmethod
    def read(cls, fd):
        data = unpack("<12f", fd.read(48))
        return cls(data[0:3], data[3:6], data[6:9], data[9:12])

    def to_mat4x4(self):
        mat = Matrix()
        mat[0][0] = self.x_axis[0]
        mat[1][0] = self.x_axis[1]
        mat[2][0] = self.x_axis[2]
        mat[3][0] = 0.0

        mat[0][1] = self.y_axis[0]
        mat[1][1] = self.y_axis[1]
        mat[2][1] = self.y_axis[2]
        mat[3][1] = 0.0

        mat[0][2] = self.z_axis[0]
        mat[1][2] = self.z_axis[1]
        mat[2][2] = self.z_axis[2]
        mat[3][2] = 0.0

        mat[0][3] = self.origin[0]
        mat[1][3] = self.origin[1]
        mat[2][3] = self.origin[2]
        mat[3][3] = 1.0

        return mat


class AffineParts:
    def __init__(self, translation, rotation, scale, scale_rotation, flip):
        self.translation = translation
        self.rotation = rotation
        self.scale = scale
        self.scale_rotation = scale_rotation
        self.flip = flip

    @classmethod
    def read(cls, fd):
        data = unpack("<3f4f3f4ff", fd.read(60))
        return cls(
            data[0:3],
            data[3:7],
            data[7:10],
            data[10:14],
            data[14])

    def to_mat4x4(self):
        mat = Matrix.Translation(self.translation)
        scale_mat = Matrix.Identity(4)
        scale_mat[0][0], scale_mat[1][1], scale_mat[2][2] = self.scale
        mat = mat @ scale_mat

        q = Quaternion((self.rotation[3], *self.rotation[:3]))
        if self.flip < 0:
            q.negate()

        rot_mat = q.to_matrix().to_4x4()
        # rot_mat[3][0], rot_mat[3][1], rot_mat[3][2], rot_mat[3][3] = self.scale_rotation
        mat = mat @ rot_mat

        return mat


class Vertex:
    def __init__(self, co, nrm, tan, bin, uv, bone_weights):
        self.co = co
        self.nrm = nrm
        self.tan = tan
        self.bin = bin
        self.uv = uv
        self.bone_weights = bone_weights

    @classmethod
    def read(cls, fd):
        data = unpack("<3f3f3f3f2fIfIfIfIfI", fd.read(92))
        return cls(
            data[0:3],
            data[3:6],
            data[6:9],
            data[9:12],
            data[12:15],
            data[15:23])


class FaceSet:
    def __init__(self, mat_index, first_face, faces_num, bones):
        self.mat_index = mat_index
        self.first_face = first_face
        self.faces_num = faces_num
        self.bones = bones

    @classmethod
    def read(cls, fd):
        mat_index, first_face, faces_num, bones_num = unpack("<4I", fd.read(16))
        bones = unpack("<%dI" % bones_num, fd.read(4 * bones_num))
        return cls(mat_index, first_face, faces_num, bones)


class Bone:
    def __init__(self, name, parent, affine_parts):
        self.name = name
        self.parent = parent
        self.affine_parts = affine_parts

    @classmethod
    def read(cls, fd):
        name = read_string(fd)
        parent = unpack("<i", fd.read(4))[0]
        affine_parts = AffineParts.read(fd)
        return cls(name, parent, affine_parts)


class Animation:
    def __init__(self, flags, duration, curves, keys, frame_tags):
        self.flags = flags
        self.duration = duration
        self.curves = curves
        self.keys = keys
        self.frame_tags = frame_tags


    @classmethod
    def read(cls, fd):
        curves, keys, frame_tags = None, {}, {}
        flags, keys_num, duration, compressed_animation = unpack("<IIfI", fd.read(16))

        if compressed_animation:
            curves_num = unpack('<I', fd.read(4))[0]
            curves = [AnimationCurve.read(fd) for _ in range(curves_num)]

        bones_num = unpack('<I', fd.read(4))[0]
        for _ in range(bones_num):
            bone = unpack('<I', fd.read(4))[0]
            vals = [AffineParts.read(fd) for k in range(keys_num)]
            keys[bone] = vals

        frame_tags_num = unpack('<I', fd.read(4))[0]
        for _ in range(frame_tags_num):
            frame = unpack('<I', fd.read(4))[0]
            frame_name = read_string(fd)
            frame_tags[frame] = frame_name

        return cls(flags, duration, curves, keys, frame_tags)


class AnimationCurve:
    def __init__(self, pos_keys, scale_keys, flip_keys, rot_keys, rot_scale_keys):
        self.pos_keys = pos_keys
        self.scale_keys = scale_keys
        self.flip_keys = flip_keys
        self.rot_keys = rot_keys
        self.rot_scale_keys = rot_scale_keys

    @classmethod
    def read(cls, fd):
        pos_keys_num = unpack('<I', fd.read(4))[0]
        pos_keys = dict(zip(unpack('<%df' % pos_keys_num, fd.read(4 * pos_keys_num)),
                            unpack('<%df' % (pos_keys_num * 3), fd.read(12 * pos_keys_num))))

        scale_keys_num = unpack('<I', fd.read(4))[0]
        scale_keys = dict(zip(unpack('<%df' % scale_keys_num, fd.read(4 * scale_keys_num)),
                              unpack('<%df' % (scale_keys_num * 3), fd.read(12 * scale_keys_num))))

        flip_keys_num = unpack('<I', fd.read(4))[0]
        flip_keys = dict(zip(unpack('<%df' % flip_keys_num, fd.read(4 * flip_keys_num)),
                             unpack('<%df' % flip_keys_num, fd.read(4 * flip_keys_num))))

        rot_keys_num = unpack('<I', fd.read(4))[0]
        rot_keys = dict(zip(unpack('<%df' % rot_keys_num, fd.read(4 * rot_keys_num)),
                            unpack('<%df' % (rot_keys_num * 4), fd.read(16 * rot_keys_num))))

        rot_scale_keys_num = unpack('<I', fd.read(4))[0]
        rot_scale_keys = dict(zip(unpack('<%df' % rot_scale_keys_num, fd.read(4 * rot_scale_keys_num)),
                                  unpack('<%df' % (rot_scale_keys_num * 4), fd.read(16 * rot_scale_keys_num))))

        return cls(pos_keys, scale_keys, flip_keys, rot_keys, rot_scale_keys)


class AnimationNode:
    def __init__(self, node_type, flags, data):
        self.node_type = node_type
        self.flags = flags
        self.data = data

    @classmethod
    def read(cls, fd):
        node_type = NodeType(unpack('<I', fd.read(4))[0])
        flags = unpack('<I', fd.read(4))[0]
        if node_type == NodeType.ANIMATION:
            data = AnimNodeAnimation.read(fd)
        elif node_type == NodeType.BLEND:
            data = AnimNodeBlend.read(fd)
        else:
            data = AnimNodeLayer.read(fd)

        return cls(node_type, flags, data)



class AnimNodeAnimation:
    def __init__(self, animation):
        self.animation = animation

    @classmethod
    def read(cls, fd):
        animation = unpack('<I', fd.read(4))[0]

        return cls(animation)


class AnimNodeBlend:
    def __init__(self, animations, param, min_val, max_val):
        self.animations = animations
        self.param = param
        self.min_val = min_val
        self.max_val = max_val

    @classmethod
    def read(cls, fd):
        param, min_val, max_val, blends_num = unpack('<IffI', fd.read(16))
        animations = unpack('<%dI' % blends_num, fd.read(4 * blends_num))

        return cls(animations, param, min_val, max_val)


class AnimNodeLayer:
    def __init__(self, animations):
        self.animations = animations

    @classmethod
    def read(cls, fd):
        layers_num = unpack('<I', fd.read(4))[0]
        animations = unpack('<%dI' % layers_num, fd.read(4 * layers_num))

        return cls(animations)


class Sequence:
    def __init__(self, name, animation_node, length):
        self.name = name
        self.animation_node = animation_node
        self.length = length

    @classmethod
    def read(cls, fd):
        name = read_string(fd)
        animation_node, length = unpack('<If', fd.read(8))

        return cls(name, animation_node, length)


class Camera:
    def __init__(self, name, bone, fov, coords):
        self.name = name
        self.bone = bone
        self.fov = fov
        self.coords = coords

    @classmethod
    def read(cls, fd):
        name = read_string(fd)
        bone, fov = unpack('<If', fd.read(8))
        coords = Coords.read(fd)

        return cls(name, bone, fov, coords)


class AttachPoint:
    def __init__(self, name, bone, coords):
        self.name = name
        self.bone = bone
        self.coords = coords

    @classmethod
    def read(cls, fd):
        name = read_string(fd)
        bone = unpack('<I', fd.read(4))[0]
        coords = Coords.read(fd)

        return cls(name, bone, coords)
