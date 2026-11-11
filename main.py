"""
================================================================
PROCEDURAL CASTLE WITH FULLY-VISIBLE INTERIOR
================================================================
A complete procedural Blender scene that builds a medieval castle
with a deliberately-lowered front wall so the entire interior is
visible from the camera at once.

Key features
------------
  * Four cylindrical corner towers with conical roofs and flags
  * Curtain walls with crenellations (battlements)
  * Low front wall + gate opening + iron portcullis
  * Interior floor split into four themed rooms:
      - Throne room (center)
      - Bedroom (front-left)
      - Kitchen (front-right)
      - Library (back-left)
  * Fully furnished rooms with detailed geometry
  * Procedural stone / wood / fabric materials
  * Fireplace, chandelier, candelabras, torches, banners
  * Armor stand, weapon rack, well, barrels, chests
  * Sun + interior point lights for readability
  * Cameras aimed to reveal the interior
  * GLB export ready to use anywhere

Blender compatibility: tested API for Blender 3.6 LTS and 4.x
================================================================
"""

import bpy
import bmesh
import math
import os
import sys
import traceback
import pathlib
import mathutils
from mathutils import Vector, Euler


# ================================================================
# SCENE CONSTANTS
# ================================================================
CASTLE_HALF        = 6.5       # Half width of the outer footprint
WALL_THICKNESS     = 0.6       # Curtain wall thickness
WALL_HEIGHT_BACK   = 6.0       # Height of back / side walls
WALL_HEIGHT_FRONT  = 2.5       # Front wall kept LOW for visibility
TOWER_RADIUS       = 1.8
TOWER_HEIGHT       = 9.0
TOWER_ROOF_HEIGHT  = 3.0
TOWER_SEGMENTS     = 32
CRENEL_HEIGHT      = 0.8
CRENEL_WIDTH       = 0.6
CRENEL_GAP         = 0.6
CRENEL_DEPTH       = 0.35
GATE_WIDTH         = 3.0
GATE_ARCH_HEIGHT   = 3.2
GATE_PILLAR_SIZE   = 0.7
FLOOR_THICKNESS    = 0.1
EXPORT_DIR_NAME    = "out"
EXPORT_FILENAME    = "castle.glb"


# ================================================================
# GLOBAL MATERIAL REGISTRY
# ================================================================
MATS = {}


# ================================================================
# SCENE UTILITIES
# ================================================================
def clear_scene():
    """Reset Blender to an empty scene."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in list(bpy.data.collections):
        try:
            bpy.data.collections.remove(coll)
        except Exception:
            pass


def create_collection(name):
    """Create a new collection and return it."""
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def link_to_collection(obj, collection):
    """Move `obj` from its current collections into `collection`."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)


def deselect_all():
    bpy.ops.object.select_all(action='DESELECT')


def select_only(obj):
    deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


# ================================================================
# MESH PRIMITIVE HELPERS
# ================================================================
def add_box(name, location, dimensions, material=None,
            collection=None, rotation=(0, 0, 0)):
    """Axis-aligned box of given dimensions at location."""
    bpy.ops.mesh.primitive_cube_add(
        size=1.0, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = dimensions
    bpy.ops.object.transform_apply(
        location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


def add_cylinder(name, location, radius, depth, material=None,
                 collection=None, rotation=(0, 0, 0), vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=depth, location=location,
        rotation=rotation, vertices=vertices)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


def add_cone(name, location, radius1, radius2, depth, material=None,
             collection=None, rotation=(0, 0, 0), vertices=32):
    bpy.ops.mesh.primitive_cone_add(
        radius1=radius1, radius2=radius2, depth=depth,
        location=location, rotation=rotation, vertices=vertices)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


def add_sphere(name, location, radius, material=None,
               collection=None, segments=24, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius, location=location,
        segments=segments, ring_count=rings)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


def add_torus(name, location, major_radius, minor_radius, material=None,
              collection=None, rotation=(0, 0, 0),
              major_segments=32, minor_segments=12):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius, minor_radius=minor_radius,
        location=location, rotation=rotation,
        major_segments=major_segments, minor_segments=minor_segments)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


# ================================================================
# MATERIAL BUILDERS
# ================================================================
def make_simple_material(name, color, metallic=0.0, roughness=0.8):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def make_emission_material(name, color, strength=5.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    for n in list(nodes):
        if n.type != "OUTPUT_MATERIAL":
            nodes.remove(n)
    output = nodes.get("Material Output")
    emit = nodes.new("ShaderNodeEmission")
    emit.location = (200, 0)
    emit.inputs["Color"].default_value = (*color, 1.0)
    emit.inputs["Strength"].default_value = strength
    mat.node_tree.links.new(
        emit.outputs["Emission"], output.inputs["Surface"])
    return mat


def make_stone_material(name="Stone", base=(0.55, 0.52, 0.48)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (700, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (400, 0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.95

    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 8.0
    noise.inputs["Detail"].default_value = 10.0
    noise.inputs["Roughness"].default_value = 0.65

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-100, 0)
    dark = (base[0] * 0.7, base[1] * 0.7, base[2] * 0.7, 1)
    light = (min(base[0] * 1.15, 1), min(base[1] * 1.15, 1),
             min(base[2] * 1.15, 1), 1)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = light

    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def make_wood_material(name="Wood", base=(0.45, 0.28, 0.15)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (700, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (400, 0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.75

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-800, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 0)
    mapping.inputs["Scale"].default_value = (1.0, 25.0, 1.0)

    wave = nodes.new("ShaderNodeTexWave")
    wave.location = (-350, 0)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    wave.inputs["Scale"].default_value = 2.5
    wave.inputs["Distortion"].default_value = 5.0
    wave.inputs["Detail"].default_value = 3.0

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-100, 0)
    dark = (base[0] * 0.6, base[1] * 0.6, base[2] * 0.6, 1)
    light = (min(base[0] * 1.25, 1), min(base[1] * 1.25, 1),
             min(base[2] * 1.25, 1), 1)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = light

    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def make_fabric_material(name, color, roughness=0.9):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = roughness

    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 70.0
    noise.inputs["Detail"].default_value = 2.0

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-100, 0)
    dark = (color[0] * 0.7, color[1] * 0.7, color[2] * 0.7, 1)
    light = (min(color[0] * 1.15, 1), min(color[1] * 1.15, 1),
             min(color[2] * 1.15, 1), 1)
    ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].color = light
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def build_all_materials():
    """Populate the MATS dictionary with every material we need."""
    MATS["stone"]       = make_stone_material("Stone",       (0.58, 0.55, 0.50))
    MATS["stone_dark"]  = make_stone_material("StoneDark",   (0.34, 0.32, 0.29))
    MATS["stone_light"] = make_stone_material("StoneLight",  (0.76, 0.73, 0.67))
    MATS["stone_floor"] = make_stone_material("StoneFloor",  (0.66, 0.63, 0.58))

    MATS["wood"]        = make_wood_material("Wood",        (0.45, 0.28, 0.15))
    MATS["wood_dark"]   = make_wood_material("WoodDark",    (0.24, 0.14, 0.07))
    MATS["wood_light"]  = make_wood_material("WoodLight",   (0.68, 0.47, 0.26))
    MATS["wood_plank"]  = make_wood_material("WoodPlank",   (0.55, 0.36, 0.20))

    MATS["iron"]        = make_simple_material("Iron",   (0.18, 0.18, 0.20), 1.0, 0.5)
    MATS["gold"]        = make_simple_material("Gold",   (0.95, 0.75, 0.25), 1.0, 0.25)
    MATS["steel"]       = make_simple_material("Steel",  (0.62, 0.62, 0.68), 1.0, 0.35)
    MATS["bronze"]      = make_simple_material("Bronze", (0.70, 0.45, 0.15), 0.9, 0.35)

    MATS["fabric_red"]    = make_fabric_material("FabricRed",    (0.55, 0.08, 0.08))
    MATS["fabric_blue"]   = make_fabric_material("FabricBlue",   (0.10, 0.15, 0.55))
    MATS["fabric_green"]  = make_fabric_material("FabricGreen",  (0.10, 0.40, 0.15))
    MATS["fabric_purple"] = make_fabric_material("FabricPurple", (0.35, 0.10, 0.45))
    MATS["fabric_white"]  = make_fabric_material("FabricWhite",  (0.92, 0.92, 0.88))
    MATS["fabric_brown"]  = make_fabric_material("FabricBrown",  (0.30, 0.20, 0.10))
    MATS["fabric_gold"]   = make_fabric_material("FabricGold",   (0.80, 0.65, 0.25))

    MATS["grass"]       = make_simple_material("Grass",  (0.16, 0.34, 0.12), 0.0, 1.0)
    MATS["dirt"]        = make_simple_material("Dirt",   (0.30, 0.22, 0.15), 0.0, 1.0)
    MATS["water"]       = make_simple_material("Water",  (0.10, 0.25, 0.50), 0.2, 0.05)
    MATS["glass"]       = make_simple_material("Glass",  (0.72, 0.82, 0.95), 0.05, 0.05)
    MATS["leather"]     = make_simple_material("Leather",(0.35, 0.20, 0.10), 0.0, 0.85)

    MATS["fire"]        = make_emission_material("Fire",        (1.0, 0.42, 0.10), 9.0)
    MATS["ember"]       = make_emission_material("Ember",       (1.0, 0.20, 0.05), 4.0)
    MATS["candle"]      = make_emission_material("Candle",      (1.0, 0.85, 0.55), 3.5)
    MATS["window_light"]= make_emission_material("WindowLight", (1.0, 0.85, 0.55), 1.5)


# ================================================================
# GROUND AND OUTDOOR
# ================================================================
def build_ground(collection):
    """Ground plane + a dirt path leading to the gate."""
    bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 0, -0.05))
    plane = bpy.context.active_object
    plane.name = "Ground"
    plane.data.materials.append(MATS["grass"])
    link_to_collection(plane, collection)

    add_box(
        "DirtPath", (0, -11.0, -0.04), (4.0, 12.0, 0.02),
        material=MATS["dirt"], collection=collection,
    )


def build_outdoor_well(collection, x, y):
    """Stone well with wooden roof."""
    add_cylinder("WellBody", (x, y, 0.6), 1.0, 1.2,
                 material=MATS["stone"], collection=collection, vertices=24)
    add_cylinder("WellInner", (x, y, 0.6), 0.85, 1.2,
                 material=MATS["stone_dark"], collection=collection, vertices=24)
    add_cylinder("WellWater", (x, y, 0.2), 0.85, 0.02,
                 material=MATS["water"], collection=collection, vertices=24)
    # Two posts
    for side, dx in [("L", -0.9), ("R", 0.9)]:
        add_box(f"WellPost_{side}", (x + dx, y, 1.85),
                (0.12, 0.12, 2.5),
                material=MATS["wood_dark"], collection=collection)
    # Roof
    add_box("WellRoof", (x, y, 3.15), (2.4, 1.6, 0.15),
            material=MATS["wood"], collection=collection)
    add_cone("WellRoofTop", (x, y, 3.45), 1.3, 0.0, 0.5,
             material=MATS["wood_dark"], collection=collection, vertices=4)
    # Bucket
    add_cylinder("WellBucket", (x, y, 2.3), 0.18, 0.25,
                 material=MATS["wood_dark"], collection=collection, vertices=12)
    add_cylinder("WellRope", (x, y, 2.75), 0.02, 0.6,
                 material=MATS["fabric_brown"], collection=collection, vertices=6)


def build_horse_trough(collection, x, y):
    """Wooden horse trough with water."""
    add_box("TroughBody", (x, y, 0.35), (2.0, 0.8, 0.7),
            material=MATS["wood_dark"], collection=collection)
    add_box("TroughWater", (x, y, 0.63), (1.85, 0.65, 0.05),
            material=MATS["water"], collection=collection)
    for i, sx in enumerate([-0.85, 0.85]):
        add_box(f"TroughLeg_{i}", (x + sx, y, 0.15),
                (0.15, 0.7, 0.3),
                material=MATS["wood_dark"], collection=collection)


# ================================================================
# STRUCTURE: WALLS
# ================================================================
def build_wall_segment(name, start, end, height, thickness,
                       material, collection):
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    angle = math.atan2(dy, dx)
    return add_box(
        name, (cx, cy, height / 2),
        (length, thickness, height),
        material=material, collection=collection,
        rotation=(0, 0, angle),
    )


def build_crenellations(name, start, end, wall_height, thickness,
                        material, collection):
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    angle = math.atan2(dy, dx)
    nx, ny = math.cos(angle), math.sin(angle)
    step = CRENEL_WIDTH + CRENEL_GAP
    n = int(length / step)
    if n < 1:
        return
    row_len = n * step - CRENEL_GAP
    off = (length - row_len) / 2
    sx = x1 + nx * off
    sy = y1 + ny * off
    for i in range(n):
        mx = sx + nx * (i * step + CRENEL_WIDTH / 2)
        my = sy + ny * (i * step + CRENEL_WIDTH / 2)
        add_box(
            f"{name}_{i}", (mx, my, wall_height + CRENEL_HEIGHT / 2),
            (CRENEL_WIDTH, thickness + CRENEL_DEPTH, CRENEL_HEIGHT),
            material=material, collection=collection,
            rotation=(0, 0, angle),
        )


def build_back_wall(collection):
    h = CASTLE_HALF
    t = WALL_THICKNESS
    build_wall_segment("BackWall", (-h, h), (h, h),
                       WALL_HEIGHT_BACK, t, MATS["stone"], collection)
    build_crenellations("BackCrenel", (-h, h), (h, h),
                        WALL_HEIGHT_BACK, t, MATS["stone"], collection)
    for i, x in enumerate([-4.0, 0.0, 4.0]):
        add_box(f"BackButtress_{i}", (x, h + t / 2, WALL_HEIGHT_BACK / 2),
                (0.6, 0.4, WALL_HEIGHT_BACK),
                material=MATS["stone_dark"], collection=collection)


def build_left_wall(collection):
    h = CASTLE_HALF
    t = WALL_THICKNESS
    build_wall_segment("LeftWall", (-h, -h), (-h, h),
                       WALL_HEIGHT_BACK, t, MATS["stone"], collection)
    build_crenellations("LeftCrenel", (-h, -h), (-h, h),
                        WALL_HEIGHT_BACK, t, MATS["stone"], collection)
    for i, y in enumerate([-4.0, 0.0, 4.0]):
        add_box(f"LeftButtress_{i}", (-h - t / 2, y, WALL_HEIGHT_BACK / 2),
                (0.4, 0.6, WALL_HEIGHT_BACK),
                material=MATS["stone_dark"], collection=collection)


def build_right_wall(collection):
    h = CASTLE_HALF
    t = WALL_THICKNESS
    build_wall_segment("RightWall", (h, -h), (h, h),
                       WALL_HEIGHT_BACK, t, MATS["stone"], collection)
    build_crenellations("RightCrenel", (h, -h), (h, h),
                        WALL_HEIGHT_BACK, t, MATS["stone"], collection)
    for i, y in enumerate([-4.0, 0.0, 4.0]):
        add_box(f"RightButtress_{i}", (h + t / 2, y, WALL_HEIGHT_BACK / 2),
                (0.4, 0.6, WALL_HEIGHT_BACK),
                material=MATS["stone_dark"], collection=collection)


def build_front_wall(collection):
    h = CASTLE_HALF
    t = WALL_THICKNESS
    half_gate = GATE_WIDTH / 2
    build_wall_segment("FrontWallLeft", (-h, -h), (-half_gate, -h),
                       WALL_HEIGHT_FRONT, t, MATS["stone"], collection)
    build_crenellations("FrontLeftCrenel", (-h, -h), (-half_gate, -h),
                        WALL_HEIGHT_FRONT, t, MATS["stone"], collection)
    build_wall_segment("FrontWallRight", (half_gate, -h), (h, -h),
                       WALL_HEIGHT_FRONT, t, MATS["stone"], collection)
    build_crenellations("FrontRightCrenel", (half_gate, -h), (h, -h),
                        WALL_HEIGHT_FRONT, t, MATS["stone"], collection)


# ================================================================
# STRUCTURE: TOWERS
# ================================================================
def build_tower(name, x, y, collection):
    add_cylinder(f"{name}_Body", (x, y, TOWER_HEIGHT / 2),
                 TOWER_RADIUS, TOWER_HEIGHT,
                 material=MATS["stone"], collection=collection,
                 vertices=TOWER_SEGMENTS)
    add_cylinder(f"{name}_Plinth", (x, y, 0.4),
                 TOWER_RADIUS + 0.25, 0.8,
                 material=MATS["stone_dark"], collection=collection,
                 vertices=TOWER_SEGMENTS)
    add_cylinder(f"{name}_Belt", (x, y, TOWER_HEIGHT - 0.6),
                 TOWER_RADIUS + 0.15, 0.3,
                 material=MATS["stone_dark"], collection=collection,
                 vertices=TOWER_SEGMENTS)

    n_merlons = 12
    for i in range(n_merlons):
        angle = 2 * math.pi * i / n_merlons
        mx = x + math.cos(angle) * (TOWER_RADIUS + 0.2)
        my = y + math.sin(angle) * (TOWER_RADIUS + 0.2)
        add_box(f"{name}_Merlon_{i}",
                (mx, my, TOWER_HEIGHT + CRENEL_HEIGHT / 2),
                (CRENEL_WIDTH, CRENEL_WIDTH, CRENEL_HEIGHT),
                material=MATS["stone"], collection=collection,
                rotation=(0, 0, angle))

    add_cone(f"{name}_Roof",
             (x, y, TOWER_HEIGHT + CRENEL_HEIGHT + TOWER_ROOF_HEIGHT / 2),
             TOWER_RADIUS + 0.3, 0.0, TOWER_ROOF_HEIGHT,
             material=MATS["stone_dark"], collection=collection,
             vertices=TOWER_SEGMENTS)

    add_cylinder(f"{name}_Pole",
                 (x, y, TOWER_HEIGHT + CRENEL_HEIGHT + TOWER_ROOF_HEIGHT + 1.2),
                 0.05, 2.4,
                 material=MATS["iron"], collection=collection, vertices=8)
    add_box(f"{name}_Flag",
            (x + 0.6, y, TOWER_HEIGHT + CRENEL_HEIGHT + TOWER_ROOF_HEIGHT + 2.1),
            (1.2, 0.02, 0.6),
            material=MATS["fabric_red"], collection=collection)

    # Arrow slit facing front
    add_box(f"{name}_Window",
            (x + math.cos(math.radians(-90)) * (TOWER_RADIUS - 0.05),
             y + math.sin(math.radians(-90)) * (TOWER_RADIUS - 0.05),
             TOWER_HEIGHT * 0.55),
            (0.15, 0.4, 1.2),
            material=MATS["stone_dark"], collection=collection)


# ================================================================
# STRUCTURE: GATE
# ================================================================
def build_gate(collection):
    y = -CASTLE_HALF
    half_gate = GATE_WIDTH / 2
    for side, sx in [("L", -half_gate - GATE_PILLAR_SIZE / 2),
                     ("R", half_gate + GATE_PILLAR_SIZE / 2)]:
        add_box(f"GatePillar_{side}",
                (sx, y, GATE_ARCH_HEIGHT / 2),
                (GATE_PILLAR_SIZE, GATE_PILLAR_SIZE, GATE_ARCH_HEIGHT),
                material=MATS["stone_dark"], collection=collection)
        add_box(f"GatePillarCap_{side}",
                (sx, y, GATE_ARCH_HEIGHT + 0.15),
                (GATE_PILLAR_SIZE + 0.2, GATE_PILLAR_SIZE + 0.2, 0.3),
                material=MATS["stone"], collection=collection)
    add_box("GateLintel", (0, y, GATE_ARCH_HEIGHT + 0.3),
            (GATE_WIDTH + 2 * GATE_PILLAR_SIZE, WALL_THICKNESS + 0.1, 0.4),
            material=MATS["stone_dark"], collection=collection)

    n_bars = 7
    for i in range(n_bars):
        bx = -half_gate + 0.2 + i * (GATE_WIDTH - 0.4) / (n_bars - 1)
        add_box(f"Portcullis_Bar_{i}",
                (bx, y, GATE_ARCH_HEIGHT * 0.72),
                (0.08, 0.08, GATE_ARCH_HEIGHT * 0.5),
                material=MATS["iron"], collection=collection)
    for j, z in enumerate([GATE_ARCH_HEIGHT * 0.52, GATE_ARCH_HEIGHT * 0.88]):
        add_box(f"Portcullis_HBar_{j}", (0, y, z),
                (GATE_WIDTH - 0.2, 0.08, 0.08),
                material=MATS["iron"], collection=collection)


# ================================================================
# FLOOR
# ================================================================
def build_floor(collection):
    inner = CASTLE_HALF - WALL_THICKNESS / 2 - 0.05
    add_box("FloorBase", (0, 0, FLOOR_THICKNESS / 2 - 0.02),
            (inner * 2, inner * 2, FLOOR_THICKNESS),
            material=MATS["stone_floor"], collection=collection)

    add_box("ThroneRoomFloor", (0, 2.5, FLOOR_THICKNESS + 0.005),
            (7.0, 8.0, 0.02),
            material=MATS["wood_light"], collection=collection)
    add_box("BedroomFloor", (-3.5, -3.0, FLOOR_THICKNESS + 0.005),
            (4.5, 4.5, 0.02),
            material=MATS["wood"], collection=collection)
    add_box("KitchenFloor", (3.5, -3.0, FLOOR_THICKNESS + 0.005),
            (4.5, 4.5, 0.02),
            material=MATS["stone_dark"], collection=collection)
    add_box("LibraryFloor", (-3.5, 3.5, FLOOR_THICKNESS + 0.005),
            (4.5, 4.5, 0.02),
            material=MATS["wood_dark"], collection=collection)


# ================================================================
# INTERIOR PARTITION WALLS
# ================================================================
def build_partition_walls(collection):
    h = 1.4
    t = 0.2
    # Bedroom on left-front, Kitchen on right-front
    add_box("PartBed_K", (0.0, -2.0, h / 2), (t, 4.0, h),
            material=MATS["stone"], collection=collection)
    # Library partition (left-back)
    add_box("PartBed_Lib", (-2.0, 0.5, h / 2), (t, 5.0, h),
            material=MATS["stone"], collection=collection)
    # Front walls of the rooms
    add_box("PartFrontBed", (-4.0, -2.5, h / 2), (5.0, t, h),
            material=MATS["stone"], collection=collection)
    add_box("PartFrontKit", (4.0, -2.5, h / 2), (5.0, t, h),
            material=MATS["stone"], collection=collection)
    # Short wall between throne room and library back
    add_box("PartBackLib", (-1.0, 5.5, h / 2), (0.2, 2.0, h),
            material=MATS["stone"], collection=collection)


# ================================================================
# FURNITURE: THRONE ROOM
# ================================================================
def build_dais(collection):
    add_box("DaisStep1", (0, 4.7, 0.15), (6.0, 3.0, 0.3),
            material=MATS["stone_light"], collection=collection)
    add_box("DaisStep2", (0, 5.0, 0.45), (4.5, 2.4, 0.3),
            material=MATS["stone_light"], collection=collection)
    add_box("DaisRug", (0, 5.0, 0.61), (4.2, 2.1, 0.02),
            material=MATS["fabric_red"], collection=collection)


def build_throne(collection):
    add_box("ThroneSeat", (0, 5.0, 0.95), (1.4, 1.2, 0.2),
            material=MATS["wood_dark"], collection=collection)
    add_box("ThroneBack", (0, 5.55, 1.7), (1.4, 0.15, 1.6),
            material=MATS["wood_dark"], collection=collection)
    add_box("ThroneBackTop", (0, 5.55, 2.6), (1.6, 0.2, 0.3),
            material=MATS["gold"], collection=collection)
    for i, dx in enumerate([-0.6, -0.2, 0.2, 0.6]):
        add_box(f"ThroneSpire_{i}", (dx, 5.55, 2.85),
                (0.1, 0.1, 0.25),
                material=MATS["gold"], collection=collection)
    for side, sx in [("L", -0.7), ("R", 0.7)]:
        add_box(f"ThroneArm_{side}", (sx, 5.0, 1.15),
                (0.12, 1.2, 0.4),
                material=MATS["wood_dark"], collection=collection)
        add_sphere(f"ThroneKnob_{side}", (sx, 4.4, 1.4), 0.08,
                   material=MATS["gold"], collection=collection)
    add_box("ThroneCushion", (0, 5.0, 1.1), (1.2, 1.0, 0.12),
            material=MATS["fabric_red"], collection=collection)
    for i, (dx, dy) in enumerate([(-0.6, -0.5), (0.6, -0.5),
                                  (-0.6, 0.5), (0.6, 0.5)]):
        add_box(f"ThroneLeg_{i}", (dx, 5.0 + dy, 0.75),
                (0.15, 0.15, 0.4),
                material=MATS["wood_dark"], collection=collection)


def build_long_table(collection):
    cx, cy = 0.0, 1.5
    top_z = 0.9
    tlen, twid = 4.5, 1.3
    add_box("LongTableTop", (cx, cy, top_z), (tlen, twid, 0.1),
            material=MATS["wood"], collection=collection)
    for i, dx in enumerate([-2.0, 0.0, 2.0]):
        for side, dy in [("F", -0.5), ("B", 0.5)]:
            add_box(f"LongTableLeg_{i}_{side}",
                    (cx + dx, cy + dy, top_z / 2 - 0.02),
                    (0.15, 0.15, top_z - 0.1),
                    material=MATS["wood_dark"], collection=collection)
    add_box("LongTableRunner", (cx, cy, top_z + 0.06),
            (tlen * 0.95, 0.4, 0.02),
            material=MATS["fabric_red"], collection=collection)

    for i, dx in enumerate([-1.8, -1.0, -0.2, 0.6, 1.4, 2.0]):
        add_cylinder(f"Plate_{i}", (cx + dx, cy + 0.3, top_z + 0.12),
                     0.16, 0.03,
                     material=MATS["steel"], collection=collection, vertices=16)
        add_cylinder(f"Goblet_{i}", (cx + dx, cy - 0.3, top_z + 0.18),
                     0.05, 0.18,
                     material=MATS["gold"], collection=collection, vertices=12)


def build_chair(name, location, collection, rotation=0):
    x, y, z = location
    seat_h = 0.45
    add_box(f"{name}_Seat", (x, y, z + seat_h),
            (0.5, 0.5, 0.06),
            material=MATS["wood"], collection=collection,
            rotation=(0, 0, rotation))
    for i, (dx, dy) in enumerate([(-0.2, -0.2), (0.2, -0.2),
                                  (-0.2, 0.2), (0.2, 0.2)]):
        add_box(f"{name}_Leg_{i}", (x + dx, y + dy, z + seat_h / 2),
                (0.05, 0.05, seat_h),
                material=MATS["wood_dark"], collection=collection)
    add_box(f"{name}_Back", (x, y + 0.2, z + seat_h + 0.3),
            (0.5, 0.06, 0.6),
            material=MATS["wood"], collection=collection,
            rotation=(0, 0, rotation))


def build_chairs_around_table(collection):
    cx, cy = 0.0, 1.5
    positions = [
        (-1.8, cy - 1.0), (-0.6, cy - 1.0), (0.6, cy - 1.0), (1.8, cy - 1.0),
        (-1.8, cy + 1.0), (-0.6, cy + 1.0), (0.6, cy + 1.0), (1.8, cy + 1.0),
    ]
    for i, (x, y) in enumerate(positions):
        rot = 0 if y > cy else math.pi
        build_chair(f"Chair_{i}", (x, y, 0.0), collection, rotation=rot)


def build_rug(collection, name, location, size, material):
    add_box(name, location, (size[0], size[1], 0.02),
            material=material, collection=collection)


def build_chandelier(collection):
    cx, cy, cz = 0.0, 1.5, 4.2
    add_cylinder("ChandelierChain", (cx, cy, cz + 1.5),
                 0.03, 3.0, material=MATS["iron"],
                 collection=collection, vertices=8)
    add_torus("ChandelierRing", (cx, cy, cz), 0.7, 0.08,
              material=MATS["iron"], collection=collection)
    add_cylinder("ChandelierHub", (cx, cy, cz + 0.1), 0.15, 0.2,
                 material=MATS["iron"], collection=collection, vertices=12)
    n = 8
    for i in range(n):
        angle = 2 * math.pi * i / n
        x = cx + math.cos(angle) * 0.7
        y = cy + math.sin(angle) * 0.7
        add_cylinder(f"ChandCandle_{i}", (x, y, cz + 0.2),
                     0.04, 0.2,
                     material=MATS["fabric_white"],
                     collection=collection, vertices=8)
        add_sphere(f"ChandFlame_{i}", (x, y, cz + 0.35), 0.05,
                   material=MATS["candle"], collection=collection,
                   segments=8, rings=6)


def build_candelabra(collection, name, x, y, z=0.0):
    add_cylinder(f"{name}_Base", (x, y, z + 0.05), 0.2, 0.1,
                 material=MATS["gold"], collection=collection, vertices=12)
    add_cylinder(f"{name}_Stem", (x, y, z + 0.5), 0.04, 1.0,
                 material=MATS["gold"], collection=collection, vertices=8)
    add_cylinder(f"{name}_Plate", (x, y, z + 1.0), 0.25, 0.05,
                 material=MATS["gold"], collection=collection, vertices=12)
    for i in range(3):
        angle = 2 * math.pi * i / 3
        dx = math.cos(angle) * 0.2
        dy = math.sin(angle) * 0.2
        add_cylinder(f"{name}_Candle_{i}", (x + dx, y + dy, z + 1.15),
                     0.04, 0.25,
                     material=MATS["fabric_white"],
                     collection=collection, vertices=8)
        add_sphere(f"{name}_Flame_{i}", (x + dx, y + dy, z + 1.33), 0.05,
                   material=MATS["candle"], collection=collection,
                   segments=8, rings=6)


def build_banner(collection, name, x, y, z, facing, color_mat):
    # Pole
    add_cylinder(f"{name}_Pole", (x, y, z + 0.5), 0.05, 3.0,
                 material=MATS["wood_dark"], collection=collection, vertices=8)
    # Fabric
    if facing == "south":
        add_box(f"{name}_Fabric", (x, y - 0.05, z - 0.3),
                (1.0, 0.03, 2.2), material=color_mat, collection=collection)
    elif facing == "north":
        add_box(f"{name}_Fabric", (x, y + 0.05, z - 0.3),
                (1.0, 0.03, 2.2), material=color_mat, collection=collection)
    elif facing == "east":
        add_box(f"{name}_Fabric", (x - 0.05, y, z - 0.3),
                (0.03, 1.0, 2.2), material=color_mat, collection=collection)
    else:  # west
        add_box(f"{name}_Fabric", (x + 0.05, y, z - 0.3),
                (0.03, 1.0, 2.2), material=color_mat, collection=collection)
    # Emblem (gold circle)
    add_torus(f"{name}_Emblem", (x, y, z - 0.5), 0.25, 0.03,
              material=MATS["gold"], collection=collection,
              rotation=(math.pi / 2, 0, 0) if facing in ("south", "north")
                       else (0, math.pi / 2, 0))


def build_torch(collection, name, x, y, z, side):
    add_cylinder(f"{name}_Bracket", (x, y, z), 0.05, 0.4,
                 material=MATS["iron"], collection=collection, vertices=8,
                 rotation=(math.pi / 2 if side in ("left", "right") else 0,
                           0, 0))
    add_cone(f"{name}_Holder", (x, y, z + 0.1), 0.15, 0.08, 0.2,
             material=MATS["iron"], collection=collection, vertices=8)
    add_sphere(f"{name}_Flame", (x, y, z + 0.35), 0.12,
               material=MATS["fire"], collection=collection,
               segments=12, rings=8)


def build_armor_stand(collection):
    x, y = -2.5, -4.8
    add_cylinder("ArmorBase", (x, y, 0.05), 0.35, 0.1,
                 material=MATS["wood_dark"], collection=collection, vertices=12)
    add_cylinder("ArmorPole", (x, y, 1.0), 0.05, 2.0,
                 material=MATS["iron"], collection=collection, vertices=8)
    # Torso
    add_box("ArmorTorso", (x, y, 1.4), (0.5, 0.3, 0.7),
            material=MATS["steel"], collection=collection)
    # Helmet
    add_sphere("ArmorHelmet", (x, y, 1.95), 0.22,
               material=MATS["steel"], collection=collection,
               segments=16, rings=12)
    # Shoulders
    add_box("ArmorShoulders", (x, y, 1.7), (0.7, 0.35, 0.15),
            material=MATS["steel"], collection=collection)
    # Sword
    add_box("ArmorSword", (x + 0.4, y, 1.2), (0.05, 0.05, 1.0),
            material=MATS["steel"], collection=collection)
    add_box("ArmorSwordGuard", (x + 0.4, y, 1.7), (0.25, 0.1, 0.08),
            material=MATS["gold"], collection=collection)


# ================================================================
# FURNITURE: BEDROOM
# ================================================================
def build_bed(collection, name, x, y, rotation=0):
    # Frame
    add_box(f"{name}_Frame", (x, y, 0.25), (1.6, 2.2, 0.15),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))
    # Legs
    for i, (dx, dy) in enumerate([(-0.7, -1.0), (0.7, -1.0),
                                  (-0.7, 1.0), (0.7, 1.0)]):
        add_box(f"{name}_Leg_{i}", (x + dx, y + dy, 0.15),
                (0.1, 0.1, 0.3),
                material=MATS["wood_dark"], collection=collection)
    # Mattress
    add_box(f"{name}_Mattress", (x, y, 0.42), (1.5, 2.1, 0.2),
            material=MATS["fabric_white"], collection=collection,
            rotation=(0, 0, rotation))
    # Pillow
    add_box(f"{name}_Pillow", (x, y + 0.85, 0.58), (1.2, 0.4, 0.15),
            material=MATS["fabric_white"], collection=collection,
            rotation=(0, 0, rotation))
    # Blanket
    add_box(f"{name}_Blanket", (x, y - 0.3, 0.55), (1.55, 1.4, 0.06),
            material=MATS["fabric_blue"], collection=collection,
            rotation=(0, 0, rotation))
    # Headboard
    add_box(f"{name}_Headboard", (x, y + 1.15, 0.6), (1.7, 0.1, 0.8),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))


def build_nightstand(collection, name, x, y):
    add_box(f"{name}_Body", (x, y, 0.3), (0.5, 0.5, 0.6),
            material=MATS["wood_dark"], collection=collection)
    add_box(f"{name}_Top", (x, y, 0.63), (0.55, 0.55, 0.05),
            material=MATS["wood"], collection=collection)
    # Drawer
    add_box(f"{name}_Drawer", (x, y - 0.26, 0.35), (0.4, 0.03, 0.2),
            material=MATS["wood"], collection=collection)
    add_sphere(f"{name}_Knob", (x, y - 0.28, 0.35), 0.03,
               material=MATS["gold"], collection=collection,
               segments=8, rings=6)


def build_chest(collection, name, x, y, rotation=0):
    add_box(f"{name}_Body", (x, y, 0.3), (0.9, 0.55, 0.6),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))
    add_box(f"{name}_Lid", (x, y, 0.62), (0.92, 0.57, 0.08),
            material=MATS["wood"], collection=collection,
            rotation=(0, 0, rotation))
    # Iron bands
    for i, dx in enumerate([-0.3, 0.3]):
        add_box(f"{name}_Band_{i}", (x + dx, y, 0.3),
                (0.06, 0.6, 0.6),
                material=MATS["iron"], collection=collection,
                rotation=(0, 0, rotation))
    add_box(f"{name}_Lock", (x, y - 0.29, 0.35), (0.1, 0.03, 0.12),
            material=MATS["gold"], collection=collection)


def build_bedroom(collection):
    build_bed(collection, "Bed", -4.0, -3.6)
    build_nightstand(collection, "Nightstand", -4.9, -2.2)
    build_chest(collection, "Chest1", -2.7, -4.5)
    build_rug(collection, "BedroomRug", (-4.0, -3.6, 0.06),
              (2.0, 2.5), MATS["fabric_blue"])
    # Small candle on nightstand
    build_candelabra(collection, "BedroomCandelabra", -4.9, -2.2, z=0.65)


# ================================================================
# FURNITURE: LIBRARY
# ================================================================
def build_bookshelf(collection, name, x, y, rotation=0):
    # Case
    add_box(f"{name}_Case", (x, y, 1.0), (2.0, 0.4, 2.0),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))
    # Shelves
    for i, z in enumerate([0.3, 0.85, 1.4, 1.9]):
        add_box(f"{name}_Shelf_{i}", (x, y, z), (1.9, 0.45, 0.05),
                material=MATS["wood"], collection=collection,
                rotation=(0, 0, rotation))
    # Books (rows of colored boxes)
    book_colors = [MATS["fabric_red"], MATS["fabric_blue"],
                   MATS["fabric_green"], MATS["fabric_brown"],
                   MATS["fabric_gold"]]
    for shelf_i, z in enumerate([0.5, 1.05, 1.6]):
        for j in range(8):
            dx = -0.85 + j * 0.22
            mat = book_colors[(shelf_i * 3 + j) % len(book_colors)]
            add_box(f"{name}_Book_{shelf_i}_{j}",
                    (x + dx, y - 0.05, z + 0.15),
                    (0.15, 0.3, 0.3),
                    material=mat, collection=collection,
                    rotation=(0, 0, rotation))


def build_reading_table(collection):
    x, y = -3.5, 3.5
    add_box("ReadingTableTop", (x, y, 0.75), (1.2, 0.8, 0.08),
            material=MATS["wood"], collection=collection)
    for i, (dx, dy) in enumerate([(-0.5, -0.3), (0.5, -0.3),
                                  (-0.5, 0.3), (0.5, 0.3)]):
        add_box(f"ReadingTableLeg_{i}", (x + dx, y + dy, 0.37),
                (0.08, 0.08, 0.75),
                material=MATS["wood_dark"], collection=collection)
    # Book on the table
    add_box("ReadingBook", (x - 0.1, y, 0.82), (0.3, 0.4, 0.06),
            material=MATS["fabric_red"], collection=collection)
    # Candle holder
    add_cylinder("ReadingCandleBase", (x + 0.3, y, 0.82), 0.08, 0.04,
                 material=MATS["gold"], collection=collection, vertices=12)
    add_cylinder("ReadingCandle", (x + 0.3, y, 0.95), 0.03, 0.2,
                 material=MATS["fabric_white"], collection=collection, vertices=8)
    add_sphere("ReadingCandleFlame", (x + 0.3, y, 1.08), 0.04,
               material=MATS["candle"], collection=collection,
               segments=8, rings=6)


def build_stool(collection, name, x, y):
    add_box(f"{name}_Seat", (x, y, 0.4), (0.4, 0.4, 0.06),
            material=MATS["wood"], collection=collection)
    for i, (dx, dy) in enumerate([(-0.15, -0.15), (0.15, -0.15),
                                  (-0.15, 0.15), (0.15, 0.15)]):
        add_box(f"{name}_Leg_{i}", (x + dx, y + dy, 0.2),
                (0.04, 0.04, 0.4),
                material=MATS["wood_dark"], collection=collection)


def build_library(collection):
    build_bookshelf(collection, "BookshelfA", -5.0, 3.5, rotation=math.pi / 2)
    build_bookshelf(collection, "BookshelfB", -5.0, 5.2, rotation=math.pi / 2)
    build_reading_table(collection)
    build_stool(collection, "StoolA", -3.5, 2.9)
    build_rug(collection, "LibraryRug", (-3.5, 3.5, 0.06),
              (3.5, 3.0), MATS["fabric_green"])


# ================================================================
# FURNITURE: KITCHEN
# ================================================================
def build_barrel(collection, name, x, y):
    add_cylinder(f"{name}_Body", (x, y, 0.55), 0.35, 1.1,
                 material=MATS["wood_dark"], collection=collection,
                 vertices=16)
    # Iron bands
    for i, z in enumerate([0.15, 0.55, 0.95]):
        add_torus(f"{name}_Band_{i}", (x, y, z), 0.36, 0.03,
                  material=MATS["iron"], collection=collection)
    add_cylinder(f"{name}_Top", (x, y, 1.1), 0.36, 0.02,
                 material=MATS["wood"], collection=collection, vertices=16)


def build_cauldron(collection):
    x, y = 4.5, -3.5
    # Fire ring
    for i in range(6):
        angle = 2 * math.pi * i / 6
        dx = math.cos(angle) * 0.4
        dy = math.sin(angle) * 0.4
        add_box(f"CauldronStone_{i}", (x + dx, y + dy, 0.1),
                (0.15, 0.15, 0.2),
                material=MATS["stone_dark"], collection=collection,
                rotation=(0, 0, angle))
    # Ember
    add_sphere("CauldronFire", (x, y, 0.25), 0.3,
               material=MATS["ember"], collection=collection,
               segments=12, rings=8)
    # Pot
    add_sphere("CauldronPot", (x, y, 0.6), 0.4,
               material=MATS["iron"], collection=collection,
               segments=20, rings=12)
    add_cylinder("CauldronRim", (x, y, 0.95), 0.45, 0.08,
                 material=MATS["iron"], collection=collection, vertices=24)
    add_cylinder("CauldronWater", (x, y, 0.9), 0.38, 0.03,
                 material=MATS["fabric_green"], collection=collection,
                 vertices=20)


def build_sacks(collection):
    for i, (x, y, r) in enumerate([
        (3.0, -5.0, 0.35), (3.7, -5.0, 0.4), (4.4, -5.1, 0.35),
    ]):
        add_sphere(f"Sack_{i}", (x, y, r + 0.05), r,
                   material=MATS["fabric_brown"], collection=collection,
                   segments=16, rings=12)


def build_kitchen_shelf(collection):
    x, y = 6.0, -3.0
    for z in [0.8, 1.4, 2.0]:
        add_box(f"KitchenShelf_{z}", (x, y, z), (1.0, 0.25, 0.05),
                material=MATS["wood"], collection=collection)
    # Pots and pans
    add_cylinder("ShelfPotA", (x - 0.3, y, 0.95), 0.12, 0.2,
                 material=MATS["bronze"], collection=collection, vertices=12)
    add_cylinder("ShelfPotB", (x + 0.2, y, 1.55), 0.15, 0.2,
                 material=MATS["bronze"], collection=collection, vertices=12)
    add_cylinder("ShelfJug", (x - 0.2, y, 2.15), 0.1, 0.25,
                 material=MATS["fabric_white"], collection=collection,
                 vertices=12)


def build_kitchen(collection):
    build_barrel(collection, "BarrelA", 2.8, -4.8)
    build_barrel(collection, "BarrelB", 3.6, -4.8)
    build_barrel(collection, "BarrelC", 5.7, -4.5)
    build_barrel(collection, "BarrelD", 5.7, -3.8)
    build_cauldron(collection)
    build_sacks(collection)
    build_kitchen_shelf(collection)


# ================================================================
# FIREPLACE
# ================================================================
def build_fireplace(collection):
    x, y = 3.5, 5.5
    # Mantel
    add_box("FireplaceMantel", (x, y, 2.4), (2.4, 0.6, 0.3),
            material=MATS["stone_dark"], collection=collection)
    # Sides
    for side, dx in [("L", -0.9), ("R", 0.9)]:
        add_box(f"FireplaceSide_{side}", (x + dx, y, 1.2),
                (0.4, 0.5, 2.4),
                material=MATS["stone"], collection=collection)
    # Back (behind chimney)
    add_box("FireplaceBack", (x, y + 0.2, 1.2), (2.0, 0.2, 2.4),
            material=MATS["stone_dark"], collection=collection)
    # Fire
    add_sphere("FireplaceFire", (x, y - 0.1, 0.4), 0.4,
               material=MATS["fire"], collection=collection,
               segments=16, rings=12)
    add_sphere("FireplaceEmber", (x, y - 0.1, 0.15), 0.3,
               material=MATS["ember"], collection=collection,
               segments=12, rings=8)
    # Logs
    for i, (dx, dz) in enumerate([(-0.3, 0.15), (0.1, 0.15), (0.35, 0.2)]):
        add_cylinder(f"FireplaceLog_{i}", (x + dx, y - 0.05, dz),
                     0.08, 0.6,
                     material=MATS["wood_dark"], collection=collection,
                     vertices=8,
                     rotation=(0, math.pi / 2, 0))


# ================================================================
# WINDOWS IN SIDE WALLS
# ================================================================
def build_window(collection, name, x, y, wall_side):
    """Decorative window cut into a side wall (visual only)."""
    if wall_side == "left":
        add_box(f"{name}_Frame",
                (x, y, 4.5), (0.5, 1.2, 1.6),
                material=MATS["stone_dark"], collection=collection)
        add_box(f"{name}_Glass",
                (x + 0.05, y, 4.5), (0.1, 1.0, 1.4),
                material=MATS["window_light"], collection=collection)
    else:  # right
        add_box(f"{name}_Frame",
                (x, y, 4.5), (0.5, 1.2, 1.6),
                material=MATS["stone_dark"], collection=collection)
        add_box(f"{name}_Glass",
                (x - 0.05, y, 4.5), (0.1, 1.0, 1.4),
                material=MATS["window_light"], collection=collection)


def build_windows(collection):
    h = CASTLE_HALF
    for i, y in enumerate([-3.0, 0.0, 3.0]):
        build_window(collection, f"WinL_{i}", -h, y, "left")
        build_window(collection, f"WinR_{i}", h, y, "right")


# ================================================================
# BANNERS AND DECORATIONS
# ================================================================
def build_throne_room_decorations(collection):
    # Banners on back wall
    build_banner(collection, "BannerBack_C", 0.0, CASTLE_HALF - 0.35,
                 5.0, "south", MATS["fabric_red"])
    build_banner(collection, "BannerBack_L", -3.0, CASTLE_HALF - 0.35,
                 5.0, "south", MATS["fabric_red"])
    build_banner(collection, "BannerBack_R", 3.0, CASTLE_HALF - 0.35,
                 5.0, "south", MATS["fabric_red"])

    # Torches on the walls
    for i, x in enumerate([-5.8, -3.5, 3.5, 5.8]):
        build_torch(collection, f"Torch_Back_{i}", x, CASTLE_HALF - 0.35,
                    3.0, "north")
    for i, y in enumerate([-1.0, 2.0]):
        build_torch(collection, f"Torch_Left_{i}", -CASTLE_HALF + 0.35, y,
                    3.0, "left")
        build_torch(collection, f"Torch_Right_{i}", CASTLE_HALF - 0.35, y,
                    3.0, "right")

    # Candelabras beside the throne
    build_candelabra(collection, "ThroneCandelabra_L", -1.5, 5.5, z=0.6)
    build_candelabra(collection, "ThroneCandelabra_R", 1.5, 5.5, z=0.6)

    # Rug under the long table
    build_rug(collection, "ThroneRug", (0, 1.5, 0.065),
              (5.0, 4.0), MATS["fabric_purple"])


# ================================================================
# LIGHTING
# ================================================================
def build_sun(collection):
    bpy.ops.object.light_add(type='SUN', location=(10, -15, 20))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    link_to_collection(sun, collection)


def build_point_light(collection, name, x, y, z, energy=80, color=(1, 0.75, 0.4)):
    bpy.ops.object.light_add(type='POINT', location=(x, y, z))
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    light.data.color = color
    light.data.shadow_soft_size = 0.3
    link_to_collection(light, collection)


def build_lights(collection):
    build_sun(collection)
    build_point_light(collection, "L_Throne", 0, 5.0, 3.0, 60, (1, 0.8, 0.5))
    build_point_light(collection, "L_Table", 0, 1.5, 3.5, 60, (1, 0.8, 0.5))
    build_point_light(collection, "L_Chand", 0, 1.5, 4.0, 40, (1, 0.85, 0.6))
    build_point_light(collection, "L_Bed", -4.0, -3.6, 2.0, 40, (1, 0.7, 0.4))
    build_point_light(collection, "L_Lib", -3.5, 3.5, 2.0, 40, (1, 0.8, 0.5))
    build_point_light(collection, "L_Kit", 4.5, -3.5, 2.0, 50, (1, 0.6, 0.3))
    build_point_light(collection, "L_Fire", 3.5, 5.3, 1.0, 60, (1, 0.5, 0.2))


# ================================================================
# CAMERAS
# ================================================================
def aim_camera_at(camera, target):
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def build_camera(collection):
    bpy.ops.object.camera_add(location=(8.0, -20.0, 12.0))
    cam = bpy.context.active_object
    cam.name = "MainCamera"
    cam.data.lens = 32
    cam.data.sensor_width = 36
    aim_camera_at(cam, (0, 0.5, 2.0))
    bpy.context.scene.camera = cam
    link_to_collection(cam, collection)
    return cam


# ================================================================
# EXPORT
# ================================================================
def export_glb(filepath):
    """Export the full scene to GLB."""
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        use_selection=False,
        export_cameras=True,
        export_lights=True,
        export_apply=True,
        export_yup=True,
    )


def compute_output_path():
    """Return an absolute path for the output GLB."""
    try:
        blend_dir = pathlib.Path(bpy.data.filepath).parent
    except Exception:
        blend_dir = pathlib.Path.cwd()
    out_dir = blend_dir / EXPORT_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / EXPORT_FILENAME


# ================================================================
# MAIN
# ================================================================
def main():
    print("=" * 60)
    print("Building procedural castle scene…")
    print("=" * 60)

    # 1. Reset the scene
    clear_scene()

    # 2. Build materials
    build_all_materials()

    # 3. Organize objects into logical collections
    coll_ground   = create_collection("Ground")
    coll_struct   = create_collection("Structure")
    coll_towers   = create_collection("Towers")
    coll_floor    = create_collection("FloorAndWalls")
    coll_furniture= create_collection("Furniture")
    coll_decor    = create_collection("Decorations")
    coll_light    = create_collection("Lighting")
    coll_cam      = create_collection("Cameras")

    # 4. Outdoor geometry
    build_ground(coll_ground)
    build_outdoor_well(coll_ground, 10.0, -3.0)
    build_horse_trough(coll_ground, -9.0, -3.0)

    # 5. Structure
    build_back_wall(coll_struct)
    build_left_wall(coll_struct)
    build_right_wall(coll_struct)
    build_front_wall(coll_struct)
    build_gate(coll_struct)

    # 6. Towers
    build_tower("TowerBL", -CASTLE_HALF, -CASTLE_HALF, coll_towers)
    build_tower("TowerBR",  CASTLE_HALF, -CASTLE_HALF, coll_towers)
    build_tower("TowerTL", -CASTLE_HALF,  CASTLE_HALF, coll_towers)
    build_tower("TowerTR",  CASTLE_HALF,  CASTLE_HALF, coll_towers)

    # 7. Floors and interior partitions
    build_floor(coll_floor)
    build_partition_walls(coll_floor)
    build_windows(coll_struct)

    # 8. Throne room
    build_dais(coll_furniture)
    build_throne(coll_furniture)
    build_long_table(coll_furniture)
    build_chairs_around_table(coll_furniture)
    build_chandelier(coll_decor)
    build_fireplace(coll_furniture)

    # 9. Bedroom
    build_bedroom(coll_furniture)

    # 10. Library
    build_library(coll_furniture)

    # 11. Kitchen
    build_kitchen(coll_furniture)

    # 12. Decorations
    build_throne_room_decorations(coll_decor)
    build_armor_stand(coll_decor)

    # 13. Lighting
    build_lights(coll_light)

    # 14. Camera
    build_camera(coll_cam)

    # 15. Export
    out_path = compute_output_path()
    export_glb(str(out_path))
    print(f"Exported: {out_path}")
    print("Done.")


# ================================================================
# ENTRY POINT
# ================================================================
if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Blender script failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)