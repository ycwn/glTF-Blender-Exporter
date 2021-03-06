# Copyright (c) 2017 The Khronos Group Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Imports
#

import bpy
import json
import struct

from .gltf2_debug import *
from .gltf2_filter import *
from .gltf2_generate import *
from .gltf2_create import BlenderEncoder

#
# Globals
#

#
# Functions
#

def prepare(export_settings):
    """
    Stores current state of Blender and prepares for export, depending on the current export settings.
    """
    if bpy.context.active_object is not None and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    filter_apply(export_settings)

    export_settings['gltf_original_frame'] = bpy.context.scene.frame_current

    export_settings['gltf_use_no_color'] = []

    export_settings['gltf_joint_cache'] = {}

    if not export_settings['gltf_current_frame']:
        bpy.context.scene.frame_set(0)


def finish(export_settings):
    """
    Brings back Blender into its original state before export and cleans up temporary objects.
    """
    if export_settings['temporary_meshes'] is not None:
        for temporary_mesh in export_settings['temporary_meshes']:
            bpy.data.meshes.remove(temporary_mesh)

    bpy.context.scene.frame_set(export_settings['gltf_original_frame'])


def save(operator,
         context,
         export_settings):
    """
    Starts the glTF 2.0 export and saves to content either to a .gltf or .glb file.
    """

    print_console('INFO', 'Starting glTF 2.0 export')
    bpy.context.window_manager.progress_begin(0, 100)
    bpy.context.window_manager.progress_update(0)

    #

    prepare(export_settings)

    #

    mesh_list = []
    mesh_map  = export_settings['name_mapping']
    mesh_map['__default'] = export_settings['gltf_default_name']

    if export_settings['gltf_separate']:

        mesh_obj_names = [ mesh_map[x] for x in export_settings['filtered_meshes'].keys() ]

        for name, mesh in export_settings['filtered_meshes'].items():

            objects       = []
            mesh_obj_name = mesh_map[name]

            for obj in export_settings['filtered_objects']:
                if obj.name == mesh_obj_name or obj.name not in mesh_obj_names:
                    objects.append(obj)

            mesh_list.append([ name, { name: mesh }, objects ])

    else:
        mesh_list = [[ '__default', export_settings['filtered_meshes'], export_settings['filtered_objects'] ]]


    for mesh_name, mesh_data, mesh_objects in mesh_list:

        glTF = {}
        export_settings['filtered_meshes']  = mesh_data
        export_settings['filtered_objects'] = mesh_objects
        generate_glTF(operator, context, export_settings, glTF)

        #

        indent = None
        separators = separators=(',', ':')

        if export_settings['gltf_format'] == 'ASCII' and not export_settings['gltf_strip']:
            indent = 4
            # The comma is typically followed by a newline, so no trailing whitespace is needed on it.
            separators = separators=(',', ' : ')

        glTF_encoded = json.dumps(glTF, indent=indent, separators=separators, sort_keys=True, cls=BlenderEncoder)

        #

        object_name = mesh_map[mesh_name]
        file_path   = export_settings['gltf_filepath'].replace('{NAME}', object_name)
        binary_path = export_settings['gltf_binaryfilename'].replace('{NAME}', object_name)

        if export_settings['gltf_format'] == 'ASCII':
            file = open(file_path, "w", encoding="utf8", newline="\n")
            file.write(glTF_encoded)
            file.write("\n")
            file.close()

            binary = export_settings['gltf_binary']
            if len(binary) > 0 and not export_settings['gltf_embed_buffers']:
                file = open(export_settings['gltf_filedirectory'] + binary_path, "wb")
                file.write(binary)
                file.close()

        else:
            file = open(file_path, "wb")

            glTF_data = glTF_encoded.encode()
            binary = export_settings['gltf_binary']

            length_gtlf = len(glTF_data)
            spaces_gltf = (4 - (length_gtlf & 3)) & 3
            length_gtlf += spaces_gltf

            length_bin = len(binary)
            zeros_bin = (4 - (length_bin & 3)) & 3
            length_bin += zeros_bin

            length = 12 + 8 + length_gtlf
            if length_bin > 0:
                length += 8 + length_bin

            # Header (Version 2)
            file.write('glTF'.encode())
            file.write(struct.pack("I", 2))
            file.write(struct.pack("I", length))

            # Chunk 0 (JSON)
            file.write(struct.pack("I", length_gtlf))
            file.write('JSON'.encode())
            file.write(glTF_data)
            for i in range(0, spaces_gltf):
                file.write(' '.encode())

            # Chunk 1 (BIN)
            if length_bin > 0:
                file.write(struct.pack("I", length_bin))
                file.write('BIN\0'.encode())
                file.write(binary)
                for i in range(0, zeros_bin):
                    file.write('\0'.encode())

            file.close()

    #

    finish(export_settings)

    #

    print_console('INFO', 'Finished glTF 2.0 export')
    bpy.context.window_manager.progress_end()
    print_newline()

    return {'FINISHED'}
