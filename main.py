"""
================================================================
PROCEDURAL MEDIEVAL CASTLE — FULLY COLORED EDITION
================================================================
Every single mesh object has an explicit solid-color material
that survives glTF/GLB export. Procedural textures are kept
for Blender viewport only and disconnected right before export,
so glTF receives clean solid colors — nothing appears white.

Contents
--------
  * Moat, drawbridge, stairs, courtyard
  * Four corner towers with crenellations, roofs, flags
  * Curtain walls with battlements, low front wall
  * Gate with portcullis, chains, iron bars
  * Throne room: dais, throne, long table, chandelier
  * Bedroom: bed, wardrobe, mirror, nightstand, chest
  * Library: bookshelves, reading table, globe, ladder
  * Kitchen: cauldron, barrels, stove, hanging pots
  * Chapel: altar, cross, pews, candles
  * Treasure room: chests, gold piles, jeweled crown
  * Weapon rack, armor stand, trapdoor
  * Outdoor: trees, bushes, flowers, fountain, statue,
    well, benches, lamps, carts, stables, horse, catapults
  * Sun + per-room interior point lights
  * Main camera aimed at the interior
  * GLB export to out/model.glb

Blender 4.2 LTS compatible.
================================================================
"""

import bpy
import bmesh
import math
import os
import sys
import traceback
import pathlib
import random
from mathutils import Vector


# ================================================================
# SCENE CONSTANTS
# ================================================================
CASTLE_HALF        = 6.5
WALL_THICKNESS     = 0.6
WALL_HEIGHT_BACK   = 6.0
WALL_HEIGHT_FRONT  = 2.5
WALL_HEIGHT_SIDE   = 6.0
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
MOAT_WIDTH         = 3.5
MOAT_DEPTH         = 1.2
EXPORT_DIR_NAME    = "out"
EXPORT_FILENAME    = "model.glb"


# ================================================================
# GLOBAL MATERIAL REGISTRY
# ================================================================
MATS = {}


# ================================================================
# SCENE UTILITIES
# ================================================================
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in list(bpy.data.collections):
        try:
            bpy.data.collections.remove(coll)
        except Exception:
            pass


def create_collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def link_to_collection(obj, collection):
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


def add_plane(name, location, size, material=None,
              collection=None, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(
        size=size, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


def add_prism(name, location, radius, depth, sides=6,
              material=None, collection=None, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=depth, vertices=sides,
        location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


# ================================================================
# MATERIAL BUILDERS — ALL SET SOLID BASE COLOR FOR GLTF
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
    """Stone material — sets SOLID Base Color for glTF, keeps procedural
    noise for Blender viewport only."""
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
    # ⚠️ SOLID BASE COLOR — glTF uses this directly
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)

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
    mat["base_color_solid"] = base
    return mat


def make_wood_material(name="Wood", base=(0.45, 0.28, 0.15)):
    """Wood material — sets SOLID Base Color for glTF."""
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
    # ⚠️ SOLID BASE COLOR
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)

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
    mat["base_color_solid"] = base
    return mat


def make_fabric_material(name, color, roughness=0.9):
    """Fabric material — sets SOLID Base Color for glTF."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = roughness
    # ⚠️ SOLID BASE COLOR
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)

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
    mat["base_color_solid"] = color
    return mat


def make_glass_material(name, color, transmission=0.9):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.05
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = transmission
    return mat


def build_all_materials():
    # --- STONE ---
    MATS["stone"]         = make_stone_material("Stone",       (0.58, 0.55, 0.50))
    MATS["stone_dark"]    = make_stone_material("StoneDark",   (0.34, 0.32, 0.29))
    MATS["stone_light"]   = make_stone_material("StoneLight",  (0.76, 0.73, 0.67))
    MATS["stone_floor"]   = make_stone_material("StoneFloor",  (0.62, 0.59, 0.55))
    MATS["stone_mossy"]   = make_stone_material("StoneMossy",  (0.42, 0.52, 0.35))
    MATS["stone_warm"]    = make_stone_material("StoneWarm",   (0.68, 0.58, 0.48))

    # --- WOOD ---
    MATS["wood"]          = make_wood_material("Wood",         (0.45, 0.28, 0.15))
    MATS["wood_dark"]     = make_wood_material("WoodDark",     (0.24, 0.14, 0.07))
    MATS["wood_light"]    = make_wood_material("WoodLight",    (0.68, 0.47, 0.26))
    MATS["wood_plank"]    = make_wood_material("WoodPlank",    (0.55, 0.36, 0.20))
    MATS["wood_oak"]      = make_wood_material("WoodOak",      (0.52, 0.35, 0.18))
    MATS["wood_walnut"]   = make_wood_material("WoodWalnut",   (0.32, 0.19, 0.10))

    # --- METALS ---
    MATS["iron"]          = make_simple_material("Iron",      (0.18, 0.18, 0.20), 1.0, 0.5)
    MATS["gold"]          = make_simple_material("Gold",      (0.95, 0.75, 0.25), 1.0, 0.25)
    MATS["steel"]         = make_simple_material("Steel",     (0.62, 0.62, 0.68), 1.0, 0.35)
    MATS["bronze"]        = make_simple_material("Bronze",    (0.70, 0.45, 0.15), 0.9, 0.35)
    MATS["silver"]        = make_simple_material("Silver",    (0.82, 0.82, 0.86), 1.0, 0.25)
    MATS["copper"]        = make_simple_material("Copper",    (0.72, 0.42, 0.20), 0.9, 0.4)

    # --- FABRIC ---
    MATS["fabric_red"]    = make_fabric_material("FabricRed",    (0.55, 0.08, 0.08))
    MATS["fabric_blue"]   = make_fabric_material("FabricBlue",   (0.10, 0.15, 0.55))
    MATS["fabric_green"]  = make_fabric_material("FabricGreen",  (0.10, 0.40, 0.15))
    MATS["fabric_purple"] = make_fabric_material("FabricPurple", (0.35, 0.10, 0.45))
    MATS["fabric_white"]  = make_fabric_material("FabricWhite",  (0.92, 0.92, 0.88))
    MATS["fabric_brown"]  = make_fabric_material("FabricBrown",  (0.30, 0.20, 0.10))
    MATS["fabric_gold"]   = make_fabric_material("FabricGold",   (0.80, 0.65, 0.25))
    MATS["fabric_black"]  = make_fabric_material("FabricBlack",  (0.05, 0.05, 0.05))
    MATS["fabric_cream"]  = make_fabric_material("FabricCream",  (0.88, 0.82, 0.70))
    MATS["fabric_teal"]   = make_fabric_material("FabricTeal",   (0.15, 0.55, 0.55))
    MATS["fabric_orange"] = make_fabric_material("FabricOrange", (0.85, 0.45, 0.10))

    # --- TERRAIN ---
    MATS["grass"]         = make_simple_material("Grass",   (0.16, 0.34, 0.12), 0.0, 1.0)
    MATS["grass_light"]   = make_simple_material("GrassLight",(0.30, 0.55, 0.20), 0.0, 1.0)
    MATS["dirt"]          = make_simple_material("Dirt",    (0.30, 0.22, 0.15), 0.0, 1.0)
    MATS["sand"]          = make_simple_material("Sand",    (0.82, 0.72, 0.52), 0.0, 1.0)
    MATS["leather"]       = make_simple_material("Leather", (0.35, 0.20, 0.10), 0.0, 0.85)

    # --- WATER & GLASS ---
    MATS["water"]         = make_simple_material("Water",     (0.10, 0.25, 0.50), 0.2, 0.05)
    MATS["water_deep"]    = make_simple_material("WaterDeep", (0.05, 0.15, 0.35), 0.2, 0.05)
    MATS["glass_blue"]    = make_glass_material("GlassBlue",   (0.55, 0.75, 0.95))
    MATS["glass_red"]     = make_glass_material("GlassRed",    (0.95, 0.35, 0.30))
    MATS["glass_green"]   = make_glass_material("GlassGreen",  (0.30, 0.85, 0.40))
    MATS["glass_yellow"]  = make_glass_material("GlassYellow", (0.95, 0.90, 0.30))

    # --- EMISSIVE ---
    MATS["fire"]          = make_emission_material("Fire",        (1.0, 0.42, 0.10), 9.0)
    MATS["ember"]         = make_emission_material("Ember",       (1.0, 0.20, 0.05), 4.0)
    MATS["candle"]        = make_emission_material("Candle",      (1.0, 0.85, 0.55), 3.5)
    MATS["window_light"]  = make_emission_material("WindowLight", (1.0, 0.85, 0.55), 1.5)
    MATS["lantern"]       = make_emission_material("Lantern",     (1.0, 0.70, 0.35), 4.0)
    MATS["torch_glow"]    = make_emission_material("TorchGlow",   (1.0, 0.55, 0.15), 5.0)

    # --- GEMS ---
    MATS["gem_ruby"]      = make_simple_material("GemRuby",     (0.85, 0.05, 0.10), 0.0, 0.1)
    MATS["gem_sapphire"]  = make_simple_material("GemSapphire", (0.10, 0.20, 0.85), 0.0, 0.1)
    MATS["gem_emerald"]   = make_simple_material("GemEmerald",  (0.05, 0.75, 0.30), 0.0, 0.1)
    MATS["gem_amethyst"]  = make_simple_material("GemAmethyst", (0.55, 0.20, 0.75), 0.0, 0.1)

    # --- FOLIAGE ---
    MATS["leaf_dark"]     = make_simple_material("LeafDark",  (0.12, 0.30, 0.10), 0.0, 1.0)
    MATS["leaf_light"]    = make_simple_material("LeafLight", (0.22, 0.48, 0.15), 0.0, 1.0)
    MATS["trunk"]         = make_simple_material("Trunk",     (0.28, 0.18, 0.10), 0.0, 0.9)


# ================================================================
# PRE-EXPORT: PREPARE MATERIALS SO GLTF SEES SOLID COLORS
# ================================================================
def prepare_materials_for_gltf():
    """Disconnect any non-image node from Base Color so glTF receives
    the SOLID default_value instead of a grey fallback."""
    fixed = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        tree = mat.node_tree
        for node in tree.nodes:
            if node.type != 'BSDF_PRINCIPLED':
                continue
            base = node.inputs.get("Base Color")
            if base and base.is_linked:
                link = base.links[0]
                from_node = link.from_node
                # Keep image textures, disconnect procedural nodes
                if from_node.type != 'TEX_IMAGE':
                    tree.links.remove(link)
                    # Re-apply the solid stored color if available
                    stored = mat.get("base_color_solid")
                    if stored:
                        base.default_value = (*stored, 1.0)
                    fixed += 1
    print(f"[PREP] Disconnected {fixed} procedural Base Color links "
          f"so glTF gets solid colors.")


def ensure_all_objects_have_materials():
    """Safety net: any mesh without a material gets a fallback color."""
    fallback = MATS.get("stone_warm")
    if fallback is None:
        fallback = make_simple_material("DefaultWarm", (0.6, 0.55, 0.5))
    missing = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and len(obj.data.materials) == 0:
            obj.data.materials.append(fallback)
            missing.append(obj.name)
    if missing:
        print(f"[SAFETY] Assigned fallback material to "
              f"{len(missing)} objects: {missing[:10]}"
              f"{'...' if len(missing) > 10 else ''}")
    else:
        print("[SAFETY] Every mesh object has a material ✅")


def report_materials_summary():
    """Print a summary of all materials and their base colors."""
    print("=" * 60)
    print(f"Materials in scene: {len(bpy.data.materials)}")
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                c = node.inputs["Base Color"].default_value
                print(f"  {mat.name:20s}  RGB=({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})")
                break
    print("=" * 60)


# ================================================================
# GROUND
# ================================================================
def build_ground(collection):
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.05))
    plane = bpy.context.active_object
    plane.name = "Ground"
    plane.data.materials.append(MATS["grass"])
    link_to_collection(plane, collection)

    add_box("DirtPath", (0, -14.0, -0.04), (4.0, 16.0, 0.02),
            material=MATS["dirt"], collection=collection)

    # Small grass patches for variation
    for i, (x, y) in enumerate([
        (-6.0, 8.0), (5.0, 9.0), (-8.0, -12.0), (7.0, -13.0),
        (-12.0, 0.0), (13.0, 1.0),
    ]):
        add_plane(f"GrassPatch_{i}", (x, y, -0.03), 3.0,
                  material=MATS["grass_light"], collection=collection)


# ================================================================
# MOAT
# ================================================================
def build_moat(collection):
    outer = CASTLE_HALF + MOAT_WIDTH
    inner = CASTLE_HALF + 0.6

    # Moat floor (dirt) and water
    for name, x, y, sx, sy in [
        ("MoatBack",  0, outer,  (inner + 1.0) * 2, MOAT_WIDTH),
        ("MoatFront", 0, -outer, (inner + 1.0) * 2, MOAT_WIDTH),
        ("MoatLeft",  -outer, 0, MOAT_WIDTH, inner * 2 + 1.0),
        ("MoatRight", outer, 0,  MOAT_WIDTH, inner * 2 + 1.0),
    ]:
        add_box(name + "Floor", (x, y, -MOAT_DEPTH),
                (sx, sy, 0.05), material=MATS["dirt"],
                collection=collection)
        add_box(name + "Water", (x, y, -MOAT_DEPTH + 0.4),
                (sx, sy, 0.02), material=MATS["water"],
                collection=collection)

    # Stone banks
    for name, x, y, sx, sy in [
        ("BankBack",  0, inner,  (inner + 1.0) * 2, 0.4),
        ("BankFront", 0, -inner, (inner + 1.0) * 2, 0.4),
        ("BankLeft",  -inner, 0, 0.4, inner * 2 + 1.0),
        ("BankRight", inner, 0,  0.4, inner * 2 + 1.0),
    ]:
        add_box(name, (x, y, 0.1), (sx, sy, 0.2),
                material=MATS["stone_mossy"],
                collection=collection)

    # Reeds
    random.seed(42)
    for i in range(24):
        side = i % 4
        if side == 0:
            px = -outer + MOAT_WIDTH * (0.3 + 0.4 * random.random())
            py = outer + MOAT_WIDTH * 0.45
        elif side == 1:
            px = -outer + MOAT_WIDTH * (0.3 + 0.4 * random.random())
            py = -outer - MOAT_WIDTH * 0.45
        elif side == 2:
            px = -outer - MOAT_WIDTH * 0.45
            py = -outer + MOAT_WIDTH * (0.3 + 0.4 * random.random())
        else:
            px = outer + MOAT_WIDTH * 0.45
            py = -outer + MOAT_WIDTH * (0.3 + 0.4 * random.random())
        add_cylinder(f"Reed_{i}", (px, py, -MOAT_DEPTH + 0.9),
                     0.02, 1.0, material=MATS["grass"],
                     collection=collection, vertices=6)


# ================================================================
# DRAWBRIDGE
# ================================================================
def build_drawbridge(collection):
    outer = CASTLE_HALF + MOAT_WIDTH
    front_y = -CASTLE_HALF
    far_y = -outer - 0.5
    length = abs(front_y - far_y)
    cy = (front_y + far_y) / 2

    n_planks = 20
    plank_len = length / n_planks
    for i in range(n_planks):
        py = far_y + (i + 0.5) * plank_len
        add_box(f"BridgePlank_{i}", (0, py, 0.15),
                (GATE_WIDTH + 0.2, plank_len * 0.9, 0.08),
                material=MATS["wood_plank"], collection=collection)

    for side, sx in [("L", -GATE_WIDTH / 2 - 0.15),
                     ("R", GATE_WIDTH / 2 + 0.15)]:
        add_box(f"BridgeRail_{side}", (sx, cy, 0.6),
                (0.1, length, 0.1),
                material=MATS["wood_dark"], collection=collection)
        for i in range(6):
            py = far_y + (i + 0.5) * (length / 6)
            add_box(f"BridgePost_{side}_{i}", (sx, py, 0.4),
                    (0.1, 0.1, 0.5),
                    material=MATS["wood_dark"], collection=collection)

    for side, sx in [("L", -GATE_WIDTH / 2 - 0.15),
                     ("R", GATE_WIDTH / 2 + 0.15)]:
        add_cylinder(f"BridgeChain_{side}", (sx, front_y - 0.2, 1.8),
                     0.03, 2.4, material=MATS["iron"],
                     collection=collection, vertices=8,
                     rotation=(math.radians(30), 0, 0))


# ================================================================
# STAIRS
# ================================================================
def build_stairs(collection):
    outer = CASTLE_HALF + MOAT_WIDTH
    stairs_start = -outer - 1.0
    n_steps = 4
    for i in range(n_steps):
        z = 0.1 + i * 0.08
        y = stairs_start + i * 0.35
        add_box(f"Stair_{i}", (0, y, z),
                (GATE_WIDTH + 0.4, 0.35, z * 2),
                material=MATS["stone_light"], collection=collection)

    add_box("GateCourtyard", (0, -outer - 2.5, 0.02),
            (GATE_WIDTH + 2.0, 2.0, 0.05),
            material=MATS["stone_light"], collection=collection)


# ================================================================
# TREES
# ================================================================
def build_tree(collection, name, x, y, scale=1.0, seed=0):
    trunk_height = 2.5 * scale
    add_cylinder(f"{name}_Trunk", (x, y, trunk_height / 2),
                 0.25 * scale, trunk_height,
                 material=MATS["trunk"], collection=collection, vertices=8)

    for i, (dx, dy, dz, ang) in enumerate([
        (0.3, 0.3, 1.8, 0.7),
        (-0.3, -0.2, 2.1, -0.9),
        (0.0, 0.4, 2.4, 1.2),
    ]):
        bx = x + dx * scale
        by = y + dy * scale
        bz = dz * scale
        add_cylinder(f"{name}_Branch_{i}", (bx, by, bz),
                     0.08 * scale, 0.8 * scale,
                     material=MATS["trunk"],
                     collection=collection, vertices=6,
                     rotation=(0, ang, 0))

    rng = random.Random(seed)
    for i in range(3):
        ox = rng.uniform(-0.4, 0.4) * scale
        oy = rng.uniform(-0.4, 0.4) * scale
        oz = (2.8 + i * 0.5) * scale
        rad = (0.9 - i * 0.15) * scale
        mat = MATS["leaf_dark"] if i % 2 == 0 else MATS["leaf_light"]
        add_sphere(f"{name}_Foliage_{i}", (x + ox, y + oy, oz),
                   rad, material=mat,
                   collection=collection, segments=16, rings=12)


def build_trees(collection):
    positions = [
        (-15.0, -8.0, 1.2, 1), (-13.0, -14.0, 1.0, 2),
        (14.0, -10.0, 1.3, 3), (16.0, -15.0, 1.1, 4),
        (-18.0, 3.0, 1.4, 5), (18.0, 4.0, 1.2, 6),
        (0.0, 15.0, 1.5, 7), (-8.0, 14.0, 1.1, 8),
        (9.0, 16.0, 1.3, 9), (-16.0, -18.0, 1.2, 10),
        (18.0, -18.0, 1.0, 11),
    ]
    for i, (x, y, s, seed) in enumerate(positions):
        build_tree(collection, f"Tree_{i}", x, y, scale=s, seed=seed)


def build_bush(collection, name, x, y, scale=1.0):
    add_sphere(f"{name}_Main", (x, y, 0.4 * scale), 0.5 * scale,
               material=MATS["leaf_dark"], collection=collection,
               segments=14, rings=10)
    add_sphere(f"{name}_Side1", (x + 0.3 * scale, y + 0.1 * scale,
                                  0.35 * scale), 0.35 * scale,
               material=MATS["leaf_light"], collection=collection,
               segments=12, rings=8)
    add_sphere(f"{name}_Side2", (x - 0.25 * scale, y - 0.15 * scale,
                                  0.32 * scale), 0.32 * scale,
               material=MATS["leaf_light"], collection=collection,
               segments=12, rings=8)


def build_bushes(collection):
    positions = [
        (-10.0, -5.0, 0.9), (-10.5, -8.0, 1.1), (11.0, -6.5, 1.0),
        (12.5, -3.0, 0.8), (-12.0, 2.0, 1.0), (13.0, 2.5, 0.9),
        (0.0, 12.0, 1.2), (-5.0, 11.5, 1.0), (5.0, 12.5, 0.9),
    ]
    for i, (x, y, s) in enumerate(positions):
        build_bush(collection, f"Bush_{i}", x, y, s)


def build_flowers(collection):
    rng = random.Random(101)
    colors = ["fabric_red", "fabric_blue", "fabric_purple",
              "fabric_white", "fabric_gold", "fabric_orange"]
    patches = [
        (-9.0, -6.0), (10.0, -7.0), (-11.0, 1.5),
        (11.5, 1.5), (0.0, 11.0), (-4.0, 11.0), (4.0, 12.0),
    ]
    for pi, (px, py) in enumerate(patches):
        for fi in range(6):
            ox = rng.uniform(-0.6, 0.6)
            oy = rng.uniform(-0.6, 0.6)
            mat = MATS[colors[fi % len(colors)]]
            add_cylinder(f"Flower_{pi}_{fi}_Stem",
                         (px + ox, py + oy, 0.1),
                         0.015, 0.2,
                         material=MATS["grass"],
                         collection=collection, vertices=4)
            add_sphere(f"Flower_{pi}_{fi}_Head",
                       (px + ox, py + oy, 0.22),
                       0.06, material=mat,
                       collection=collection, segments=8, rings=6)


# ================================================================
# OUTDOOR FURNITURE
# ================================================================
def build_well(collection, x, y):
    add_cylinder("WellBody", (x, y, 0.6), 1.0, 1.2,
                 material=MATS["stone"], collection=collection, vertices=24)
    add_cylinder("WellInner", (x, y, 0.6), 0.85, 1.2,
                 material=MATS["stone_dark"], collection=collection, vertices=24)
    add_cylinder("WellWater", (x, y, 0.2), 0.85, 0.02,
                 material=MATS["water"], collection=collection, vertices=24)
    for side, dx in [("L", -0.9), ("R", 0.9)]:
        add_box(f"WellPost_{side}", (x + dx, y, 1.85),
                (0.12, 0.12, 2.5),
                material=MATS["wood_dark"], collection=collection)
    add_box("WellRoof", (x, y, 3.15), (2.4, 1.6, 0.15),
            material=MATS["wood"], collection=collection)
    add_cone("WellRoofTop", (x, y, 3.45), 1.3, 0.0, 0.5,
             material=MATS["wood_dark"], collection=collection, vertices=4)
    add_cylinder("WellBucket", (x, y, 2.3), 0.18, 0.25,
                 material=MATS["wood_dark"], collection=collection, vertices=12)
    add_cylinder("WellRope", (x, y, 2.75), 0.02, 0.6,
                 material=MATS["fabric_brown"], collection=collection, vertices=6)


def build_horse_trough(collection, x, y):
    add_box("TroughBody", (x, y, 0.35), (2.0, 0.8, 0.7),
            material=MATS["wood_dark"], collection=collection)
    add_box("TroughWater", (x, y, 0.63), (1.85, 0.65, 0.05),
            material=MATS["water"], collection=collection)
    for i, sx in enumerate([-0.85, 0.85]):
        add_box(f"TroughLeg_{i}", (x + sx, y, 0.15),
                (0.15, 0.7, 0.3),
                material=MATS["wood_dark"], collection=collection)


def build_fountain(collection, x, y):
    add_cylinder("FountainBase", (x, y, 0.1), 2.2, 0.2,
                 material=MATS["stone_light"], collection=collection, vertices=32)
    add_cylinder("FountainRim", (x, y, 0.35), 2.1, 0.3,
                 material=MATS["stone"], collection=collection, vertices=32)
    add_cylinder("FountainWater", (x, y, 0.46), 2.0, 0.02,
                 material=MATS["water"], collection=collection, vertices=32)
    add_cylinder("FountainPillar", (x, y, 1.4), 0.35, 2.0,
                 material=MATS["stone_light"], collection=collection, vertices=16)
    add_cylinder("FountainBowl", (x, y, 2.4), 0.8, 0.25,
                 material=MATS["stone"], collection=collection, vertices=24)
    add_cylinder("FountainBowlWater", (x, y, 2.55), 0.7, 0.02,
                 material=MATS["water"], collection=collection, vertices=24)
    add_cylinder("FountainTop", (x, y, 2.9), 0.15, 0.6,
                 material=MATS["stone_light"], collection=collection, vertices=12)
    add_sphere("FountainFinial", (x, y, 3.3), 0.22,
               material=MATS["gold"], collection=collection,
               segments=16, rings=12)
    for i in range(8):
        angle = 2 * math.pi * i / 8
        dx = math.cos(angle) * 0.4
        dy = math.sin(angle) * 0.4
        add_sphere(f"FountainJet_{i}", (x + dx, y + dy, 2.6),
                   0.06, material=MATS["water"],
                   collection=collection, segments=8, rings=6)


def build_statue(collection, x, y):
    add_box("StatuePedestal", (x, y, 0.6), (1.6, 1.6, 1.2),
            material=MATS["stone_dark"], collection=collection)
    add_box("StatuePlinth", (x, y, 1.35), (1.4, 1.4, 0.3),
            material=MATS["stone"], collection=collection)
    add_box("StatueBody", (x, y, 2.3), (0.8, 0.5, 1.4),
            material=MATS["stone_light"], collection=collection)
    add_sphere("StatueHead", (x, y, 3.2), 0.28,
               material=MATS["stone_light"], collection=collection,
               segments=16, rings=12)
    add_box("StatueSword", (x + 0.55, y, 2.0), (0.08, 0.08, 1.8),
            material=MATS["steel"], collection=collection)
    add_box("StatueSwordGuard", (x + 0.55, y, 2.8), (0.35, 0.12, 0.1),
            material=MATS["gold"], collection=collection)
    add_box("StatueShield", (x - 0.4, y, 2.4), (0.5, 0.1, 0.9),
            material=MATS["steel"], collection=collection)
    add_torus("StatueShieldRim", (x - 0.4, y, 2.4), 0.25, 0.04,
              material=MATS["gold"], collection=collection,
              rotation=(0, math.pi / 2, 0))
    add_box("StatueCape", (x, y + 0.3, 2.2), (0.9, 0.1, 1.2),
            material=MATS["fabric_red"], collection=collection)


def build_bench(collection, name, x, y, rotation=0):
    add_box(f"{name}_Seat", (x, y, 0.45), (1.6, 0.5, 0.08),
            material=MATS["wood"], collection=collection,
            rotation=(0, 0, rotation))
    add_box(f"{name}_Back", (x, y + 0.22, 0.75), (1.6, 0.08, 0.55),
            material=MATS["wood"], collection=collection,
            rotation=(0, 0, rotation))
    for i, dx in enumerate([-0.65, 0.65]):
        add_box(f"{name}_Leg_{i}", (x + dx, y, 0.22),
                (0.1, 0.45, 0.45),
                material=MATS["wood_dark"], collection=collection,
                rotation=(0, 0, rotation))


def build_benches(collection):
    build_bench(collection, "Bench1", -8.5, -7.5, 0)
    build_bench(collection, "Bench2", 8.5, -7.5, math.pi)
    build_bench(collection, "Bench3", 0.0, 10.5, math.pi)


def build_lamp_post(collection, name, x, y):
    add_cylinder(f"{name}_Pole", (x, y, 1.6), 0.08, 3.2,
                 material=MATS["iron"], collection=collection, vertices=8)
    add_cylinder(f"{name}_Base", (x, y, 0.05), 0.25, 0.15,
                 material=MATS["iron"], collection=collection, vertices=12)
    add_box(f"{name}_Bracket", (x, y - 0.35, 3.15), (0.05, 0.7, 0.05),
            material=MATS["iron"], collection=collection)
    add_cylinder(f"{name}_Lantern", (x, y - 0.7, 2.85), 0.2, 0.5,
                 material=MATS["lantern"], collection=collection, vertices=6)
    add_cone(f"{name}_Cap", (x, y - 0.7, 3.2), 0.28, 0.05, 0.2,
             material=MATS["iron"], collection=collection, vertices=6)


def build_lamps(collection):
    build_lamp_post(collection, "Lamp1", -5.0, -8.0)
    build_lamp_post(collection, "Lamp2", 5.0, -8.0)
    build_lamp_post(collection, "Lamp3", -8.0, 5.0)
    build_lamp_post(collection, "Lamp4", 8.0, 5.0)


def build_cart(collection, x, y):
    add_box("CartBed", (x, y, 0.6), (2.0, 1.2, 0.15),
            material=MATS["wood"], collection=collection)
    add_box("CartSideL", (x - 0.95, y, 0.85), (0.1, 1.2, 0.5),
            material=MATS["wood_plank"], collection=collection)
    add_box("CartSideR", (x + 0.95, y, 0.85), (0.1, 1.2, 0.5),
            material=MATS["wood_plank"], collection=collection)
    add_box("CartBack", (x, y + 0.55, 0.85), (2.0, 0.1, 0.5),
            material=MATS["wood_plank"], collection=collection)
    for side, dy in [("F", -0.7), ("B", 0.7)]:
        for lr, dx in [("L", -0.9), ("R", 0.9)]:
            add_cylinder(f"CartWheel_{side}{lr}", (x + dx, y + dy, 0.4),
                         0.4, 0.15,
                         material=MATS["wood_dark"],
                         collection=collection, vertices=16,
                         rotation=(0, math.pi / 2, 0))
            add_cylinder(f"CartHub_{side}{lr}", (x + dx, y + dy, 0.4),
                         0.1, 0.18,
                         material=MATS["iron"],
                         collection=collection, vertices=8,
                         rotation=(0, math.pi / 2, 0))
    for i in range(3):
        ox = (i - 1) * 0.4
        add_box(f"CartHay_{i}", (x + ox, y, 1.15), (0.3, 0.9, 0.4),
                material=MATS["fabric_gold"], collection=collection)


def build_carts(collection):
    build_cart(collection, -10.0, -10.0)
    build_cart(collection, 10.0, -10.5)


def build_stables(collection, x, y):
    add_box("StableFloor", (x, y, 0.05), (4.0, 3.0, 0.1),
            material=MATS["wood_plank"], collection=collection)
    add_box("StableBack", (x, y + 1.4, 1.5), (4.0, 0.2, 2.8),
            material=MATS["wood"], collection=collection)
    add_box("StableSideL", (x - 1.9, y, 1.5), (0.2, 3.0, 2.8),
            material=MATS["wood"], collection=collection)
    add_box("StableSideR", (x + 1.9, y, 1.5), (0.2, 3.0, 2.8),
            material=MATS["wood"], collection=collection)
    add_box("StableRoof", (x, y, 3.2), (4.4, 3.4, 0.2),
            material=MATS["wood_dark"], collection=collection,
            rotation=(math.radians(-10), 0, 0))
    for i, dx in enumerate([-1.2, 0.0, 1.2]):
        add_box(f"StallDivider_{i}", (x + dx, y, 1.0), (0.1, 2.8, 2.0),
                material=MATS["wood_plank"], collection=collection)
        add_box(f"StallHay_{i}", (x + dx + 0.4, y + 0.8, 0.15),
                (0.7, 0.9, 0.2),
                material=MATS["fabric_gold"], collection=collection)
        add_cylinder(f"StallBucket_{i}", (x + dx + 0.5, y - 0.8, 0.2),
                     0.15, 0.3,
                     material=MATS["wood_dark"],
                     collection=collection, vertices=10)


def build_horse(collection, x, y):
    add_box("HorseBody", (x, y, 1.2), (0.9, 1.6, 0.8),
            material=MATS["fabric_brown"], collection=collection)
    add_box("HorseNeck", (x, y + 0.85, 1.55), (0.35, 0.4, 0.7),
            material=MATS["fabric_brown"], collection=collection,
            rotation=(math.radians(-30), 0, 0))
    add_box("HorseHead", (x, y + 1.15, 1.85), (0.3, 0.5, 0.35),
            material=MATS["fabric_brown"], collection=collection,
            rotation=(math.radians(20), 0, 0))
    for i, dx in enumerate([-0.1, 0.1]):
        add_cone(f"HorseEar_{i}", (x + dx, y + 1.35, 2.1),
                 0.06, 0.0, 0.2,
                 material=MATS["fabric_brown"],
                 collection=collection, vertices=6)
    for dx, dy in [(-0.35, -0.6), (0.35, -0.6),
                    (-0.35, 0.6), (0.35, 0.6)]:
        add_cylinder(f"HorseLeg_{dx}_{dy}",
                     (x + dx, y + dy, 0.45),
                     0.1, 0.9,
                     material=MATS["fabric_brown"],
                     collection=collection, vertices=8)
    add_cylinder("HorseTail", (x, y - 0.9, 1.3), 0.08, 0.7,
                 material=MATS["fabric_brown"],
                 collection=collection, vertices=6,
                 rotation=(math.radians(-20), 0, 0))
    add_box("HorseMane", (x, y + 0.85, 1.85), (0.1, 0.35, 0.4),
            material=MATS["fabric_black"], collection=collection)


def build_catapult(collection, x, y, rotation=0):
    add_box("CatapultBase", (x, y, 0.2), (2.0, 1.2, 0.4),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))
    for i, dy in enumerate([-0.55, 0.55]):
        add_box(f"CatapultRail_{i}",
                (x, y + dy, 0.6), (2.2, 0.1, 0.1),
                material=MATS["wood"], collection=collection,
                rotation=(0, 0, rotation))
    for i, dy in enumerate([-0.5, 0.5]):
        add_box(f"CatapultPost_{i}",
                (x + 0.6, y + dy, 1.0), (0.15, 0.15, 1.8),
                material=MATS["wood_dark"], collection=collection,
                rotation=(0, 0, rotation))
    add_box("CatapultArm", (x + 0.2, y, 1.4), (2.0, 0.15, 0.15),
            material=MATS["wood"], collection=collection,
            rotation=(0, math.radians(-25), rotation))
    add_cylinder("CatapultBucket", (x - 0.7, y, 1.9), 0.2, 0.25,
                 material=MATS["wood_dark"],
                 collection=collection, vertices=8)
    for i, dy in enumerate([-0.6, 0.6]):
        for j, dx in enumerate([-0.7, 0.7]):
            add_cylinder(f"CatapultWheel_{i}_{j}",
                         (x + dx, y + dy, 0.35),
                         0.35, 0.15,
                         material=MATS["wood_dark"],
                         collection=collection, vertices=14,
                         rotation=(math.pi / 2, 0, 0))


def build_catapults(collection):
    build_catapult(collection, -14.0, -3.0, math.radians(-20))
    build_catapult(collection, 14.0, -4.0, math.radians(20))


# ================================================================
# WALLS
# ================================================================
def build_wall_segment(name, start, end, height, thickness,
                       material, collection):
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    angle = math.atan2(dy, dx)
    return add_box(name, (cx, cy, height / 2),
                   (length, thickness, height),
                   material=material, collection=collection,
                   rotation=(0, 0, angle))


def build_crenellations(name, start, end, wall_height, thickness,
                        material, collection):
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
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
        add_box(f"{name}_{i}", (mx, my, wall_height + CRENEL_HEIGHT / 2),
                (CRENEL_WIDTH, thickness + CRENEL_DEPTH, CRENEL_HEIGHT),
                material=material, collection=collection,
                rotation=(0, 0, angle))


def build_back_wall(collection):
    h, t = CASTLE_HALF, WALL_THICKNESS
    build_wall_segment("BackWall", (-h, h), (h, h),
                       WALL_HEIGHT_BACK, t, MATS["stone"], collection)
    build_crenellations("BackCrenel", (-h, h), (h, h),
                        WALL_HEIGHT_BACK, t, MATS["stone"], collection)
    for i, x in enumerate([-4.0, 0.0, 4.0]):
        add_box(f"BackButtress_{i}", (x, h + t / 2, WALL_HEIGHT_BACK / 2),
                (0.6, 0.4, WALL_HEIGHT_BACK),
                material=MATS["stone_dark"], collection=collection)


def build_left_wall(collection):
    h, t = CASTLE_HALF, WALL_THICKNESS
    build_wall_segment("LeftWall", (-h, -h), (-h, h),
                       WALL_HEIGHT_SIDE, t, MATS["stone"], collection)
    build_crenellations("LeftCrenel", (-h, -h), (-h, h),
                        WALL_HEIGHT_SIDE, t, MATS["stone"], collection)
    for i, y in enumerate([-4.0, 0.0, 4.0]):
        add_box(f"LeftButtress_{i}", (-h - t / 2, y, WALL_HEIGHT_SIDE / 2),
                (0.4, 0.6, WALL_HEIGHT_SIDE),
                material=MATS["stone_dark"], collection=collection)


def build_right_wall(collection):
    h, t = CASTLE_HALF, WALL_THICKNESS
    build_wall_segment("RightWall", (h, -h), (h, h),
                       WALL_HEIGHT_SIDE, t, MATS["stone"], collection)
    build_crenellations("RightCrenel", (h, -h), (h, h),
                        WALL_HEIGHT_SIDE, t, MATS["stone"], collection)
    for i, y in enumerate([-4.0, 0.0, 4.0]):
        add_box(f"RightButtress_{i}", (h + t / 2, y, WALL_HEIGHT_SIDE / 2),
                (0.4, 0.6, WALL_HEIGHT_SIDE),
                material=MATS["stone_dark"], collection=collection)


def build_front_wall(collection):
    h, t = CASTLE_HALF, WALL_THICKNESS
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
# TOWERS
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

    for i, angle in enumerate([-90, 0, 90, 180]):
        wx = x + math.cos(math.radians(angle)) * (TOWER_RADIUS - 0.05)
        wy = y + math.sin(math.radians(angle)) * (TOWER_RADIUS - 0.05)
        add_box(f"{name}_Window_{i}",
                (wx, wy, TOWER_HEIGHT * 0.55),
                (0.15, 0.4, 1.2),
                material=MATS["stone_dark"], collection=collection,
                rotation=(0, 0, math.radians(angle)))


# ================================================================
# GATE
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


def build_partition_walls(collection):
    h, t = 1.4, 0.2
    add_box("PartBed_K", (0.0, -2.0, h / 2), (t, 4.0, h),
            material=MATS["stone"], collection=collection)
    add_box("PartBed_Lib", (-2.0, 0.5, h / 2), (t, 5.0, h),
            material=MATS["stone"], collection=collection)
    add_box("PartFrontBed", (-4.0, -2.5, h / 2), (5.0, t, h),
            material=MATS["stone"], collection=collection)
    add_box("PartFrontKit", (4.0, -2.5, h / 2), (5.0, t, h),
            material=MATS["stone"], collection=collection)
    add_box("PartBackLib", (-1.0, 5.5, h / 2), (0.2, 2.0, h),
            material=MATS["stone"], collection=collection)


# ================================================================
# THRONE ROOM
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
                     material=MATS["fabric_cream"],
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
                     material=MATS["fabric_cream"],
                     collection=collection, vertices=8)
        add_sphere(f"{name}_Flame_{i}", (x + dx, y + dy, z + 1.33), 0.05,
                   material=MATS["candle"], collection=collection,
                   segments=8, rings=6)


def build_banner(collection, name, x, y, z, facing, color_mat):
    add_cylinder(f"{name}_Pole", (x, y, z + 0.5), 0.05, 3.0,
                 material=MATS["wood_dark"], collection=collection, vertices=8)
    if facing == "south":
        add_box(f"{name}_Fabric", (x, y - 0.05, z - 0.3),
                (1.0, 0.03, 2.2), material=color_mat, collection=collection)
    elif facing == "north":
        add_box(f"{name}_Fabric", (x, y + 0.05, z - 0.3),
                (1.0, 0.03, 2.2), material=color_mat, collection=collection)
    elif facing == "east":
        add_box(f"{name}_Fabric", (x - 0.05, y, z - 0.3),
                (0.03, 1.0, 2.2), material=color_mat, collection=collection)
    else:
        add_box(f"{name}_Fabric", (x + 0.05, y, z - 0.3),
                (0.03, 1.0, 2.2), material=color_mat, collection=collection)
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
    add_box("ArmorTorso", (x, y, 1.4), (0.5, 0.3, 0.7),
            material=MATS["steel"], collection=collection)
    add_sphere("ArmorHelmet", (x, y, 1.95), 0.22,
               material=MATS["steel"], collection=collection,
               segments=16, rings=12)
    add_box("ArmorShoulders", (x, y, 1.7), (0.7, 0.35, 0.15),
            material=MATS["steel"], collection=collection)
    add_box("ArmorSword", (x + 0.4, y, 1.2), (0.05, 0.05, 1.0),
            material=MATS["steel"], collection=collection)
    add_box("ArmorSwordGuard", (x + 0.4, y, 1.7), (0.25, 0.1, 0.08),
            material=MATS["gold"], collection=collection)


# ================================================================
# BEDROOM
# ================================================================
def build_bed(collection, name, x, y, rotation=0):
    add_box(f"{name}_Frame", (x, y, 0.25), (1.6, 2.2, 0.15),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))
    for i, (dx, dy) in enumerate([(-0.7, -1.0), (0.7, -1.0),
                                   (-0.7, 1.0), (0.7, 1.0)]):
        add_box(f"{name}_Leg_{i}", (x + dx, y + dy, 0.15),
                (0.1, 0.1, 0.3),
                material=MATS["wood_dark"], collection=collection)
    add_box(f"{name}_Mattress", (x, y, 0.42), (1.5, 2.1, 0.2),
            material=MATS["fabric_white"], collection=collection,
            rotation=(0, 0, rotation))
    add_box(f"{name}_Pillow", (x, y + 0.85, 0.58), (1.2, 0.4, 0.15),
            material=MATS["fabric_white"], collection=collection,
            rotation=(0, 0, rotation))
    add_box(f"{name}_Blanket", (x, y - 0.3, 0.55), (1.55, 1.4, 0.06),
            material=MATS["fabric_blue"], collection=collection,
            rotation=(0, 0, rotation))
    add_box(f"{name}_Headboard", (x, y + 1.15, 0.6), (1.7, 0.1, 0.8),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))


def build_nightstand(collection, name, x, y):
    add_box(f"{name}_Body", (x, y, 0.3), (0.5, 0.5, 0.6),
            material=MATS["wood_dark"], collection=collection)
    add_box(f"{name}_Top", (x, y, 0.63), (0.55, 0.55, 0.05),
            material=MATS["wood"], collection=collection)
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
    for i, dx in enumerate([-0.3, 0.3]):
        add_box(f"{name}_Band_{i}", (x + dx, y, 0.3),
                (0.06, 0.6, 0.6),
                material=MATS["iron"], collection=collection,
                rotation=(0, 0, rotation))
    add_box(f"{name}_Lock", (x, y - 0.29, 0.35), (0.1, 0.03, 0.12),
            material=MATS["gold"], collection=collection)


def build_wardrobe(collection, x, y, rotation=0):
    add_box("WardrobeBody", (x, y, 1.2), (1.4, 0.6, 2.4),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))
    add_box("WardrobeTop", (x, y, 2.45), (1.5, 0.7, 0.1),
            material=MATS["wood"], collection=collection,
            rotation=(0, 0, rotation))
    add_box("WardrobeBase", (x, y, 0.05), (1.5, 0.7, 0.1),
            material=MATS["wood"], collection=collection,
            rotation=(0, 0, rotation))
    add_box("WardrobeDoorL", (x - 0.35, y - 0.31, 1.3),
            (0.65, 0.05, 2.1), material=MATS["wood"],
            collection=collection, rotation=(0, 0, rotation))
    add_box("WardrobeDoorR", (x + 0.35, y - 0.31, 1.3),
            (0.65, 0.05, 2.1), material=MATS["wood"],
            collection=collection, rotation=(0, 0, rotation))
    for side, dx in [("L", -0.05), ("R", 0.05)]:
        add_sphere(f"WardrobeHandle_{side}",
                   (x + dx, y - 0.35, 1.3), 0.04,
                   material=MATS["gold"], collection=collection,
                   segments=8, rings=6)


def build_mirror(collection, x, y, rotation=0):
    add_box("MirrorFrame", (x, y, 1.6), (0.9, 0.1, 1.6),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))
    add_box("MirrorGlass", (x, y - 0.06, 1.6), (0.75, 0.02, 1.4),
            material=MATS["silver"], collection=collection,
            rotation=(0, 0, rotation))


def build_bedroom(collection):
    build_bed(collection, "Bed", -4.0, -3.6)
    build_nightstand(collection, "Nightstand", -4.9, -2.2)
    build_chest(collection, "Chest1", -2.7, -4.5)
    build_wardrobe(collection, -5.3, -4.0, rotation=math.pi / 2)
    build_mirror(collection, -3.5, -5.6, rotation=0)
    build_rug(collection, "BedroomRug", (-4.0, -3.6, 0.06),
              (2.0, 2.5), MATS["fabric_blue"])
    build_candelabra(collection, "BedroomCandelabra", -4.9, -2.2, z=0.65)


# ================================================================
# LIBRARY
# ================================================================
def build_bookshelf(collection, name, x, y, rotation=0):
    add_box(f"{name}_Case", (x, y, 1.0), (2.0, 0.4, 2.0),
            material=MATS["wood_dark"], collection=collection,
            rotation=(0, 0, rotation))
    for i, z in enumerate([0.3, 0.85, 1.4, 1.9]):
        add_box(f"{name}_Shelf_{i}", (x, y, z), (1.9, 0.45, 0.05),
                material=MATS["wood"], collection=collection,
                rotation=(0, 0, rotation))
    book_colors = [MATS["fabric_red"], MATS["fabric_blue"],
                   MATS["fabric_green"], MATS["fabric_brown"],
                   MATS["fabric_gold"], MATS["fabric_purple"],
                   MATS["fabric_teal"]]
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
    add_box("ReadingBook", (x - 0.1, y, 0.82), (0.3, 0.4, 0.06),
            material=MATS["fabric_red"], collection=collection)
    add_cylinder("ReadingCandleBase", (x + 0.3, y, 0.82), 0.08, 0.04,
                 material=MATS["gold"], collection=collection, vertices=12)
    add_cylinder("ReadingCandle", (x + 0.3, y, 0.95), 0.03, 0.2,
                 material=MATS["fabric_cream"], collection=collection, vertices=8)
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


def build_globe(collection, x, y):
    add_cylinder("GlobeBase", (x, y, 0.1), 0.35, 0.2,
                 material=MATS["wood_dark"], collection=collection, vertices=16)
    add_cylinder("GlobeStand", (x, y, 0.55), 0.06, 0.9,
                 material=MATS["gold"], collection=collection, vertices=8)
    add_sphere("GlobeSphere", (x, y, 1.15), 0.35,
               material=MATS["fabric_blue"],
               collection=collection, segments=24, rings=16)
    add_torus("GlobeRing", (x, y, 1.15), 0.4, 0.02,
              material=MATS["gold"], collection=collection,
              rotation=(math.radians(23), 0, 0))


def build_ladder(collection, x, y, height=2.4):
    for side, dx in [("L", -0.3), ("R", 0.3)]:
        add_box(f"LadderRail_{side}", (x + dx, y, height / 2),
                (0.06, 0.06, height),
                material=MATS["wood_dark"], collection=collection)
    n_rungs = 6
    for i in range(n_rungs):
        z = 0.25 + i * (height - 0.4) / (n_rungs - 1)
        add_box(f"LadderRung_{i}", (x, y, z),
                (0.6, 0.05, 0.05),
                material=MATS["wood"], collection=collection)


def build_library(collection):
    build_bookshelf(collection, "BookshelfA", -5.0, 3.5, rotation=math.pi / 2)
    build_bookshelf(collection, "BookshelfB", -5.0, 5.2, rotation=math.pi / 2)
    build_reading_table(collection)
    build_stool(collection, "StoolA", -3.5, 2.9)
    build_globe(collection, -3.5, 5.0)
    build_ladder(collection, -5.6, 4.3, height=2.4)
    build_rug(collection, "LibraryRug", (-3.5, 3.5, 0.06),
              (3.5, 3.0), MATS["fabric_green"])


# ================================================================
# KITCHEN
# ================================================================
def build_barrel(collection, name, x, y):
    add_cylinder(f"{name}_Body", (x, y, 0.55), 0.35, 1.1,
                 material=MATS["wood_dark"], collection=collection,
                 vertices=16)
    for i, z in enumerate([0.15, 0.55, 0.95]):
        add_torus(f"{name}_Band_{i}", (x, y, z), 0.36, 0.03,
                  material=MATS["iron"], collection=collection)
    add_cylinder(f"{name}_Top", (x, y, 1.1), 0.36, 0.02,
                 material=MATS["wood"], collection=collection, vertices=16)


def build_cauldron(collection):
    x, y = 4.5, -3.5
    for i in range(6):
        angle = 2 * math.pi * i / 6
        dx = math.cos(angle) * 0.4
        dy = math.sin(angle) * 0.4
        add_box(f"CauldronStone_{i}", (x + dx, y + dy, 0.1),
                (0.15, 0.15, 0.2),
                material=MATS["stone_dark"], collection=collection,
                rotation=(0, 0, angle))
    add_sphere("CauldronFire", (x, y, 0.25), 0.3,
               material=MATS["ember"], collection=collection,
               segments=12, rings=8)
    add_sphere("CauldronPot", (x, y, 0.6), 0.4,
               material=MATS["iron"], collection=collection,
               segments=20, rings=12)
    add_cylinder("CauldronRim", (x, y, 0.95), 0.45, 0.08,
                 material=MATS["iron"], collection=collection, vertices=24)
    add_cylinder("CauldronSoup", (x, y, 0.9), 0.38, 0.03,
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
    add_cylinder("ShelfPotA", (x - 0.3, y, 0.95), 0.12, 0.2,
                 material=MATS["bronze"], collection=collection, vertices=12)
    add_cylinder("ShelfPotB", (x + 0.2, y, 1.55), 0.15, 0.2,
                 material=MATS["bronze"], collection=collection, vertices=12)
    add_cylinder("ShelfJug", (x - 0.2, y, 2.15), 0.1, 0.25,
                 material=MATS["fabric_cream"], collection=collection,
                 vertices=12)


def build_kitchen_stove(collection, x, y):
    add_box("StoveBase", (x, y, 0.4), (1.6, 1.0, 0.8),
            material=MATS["stone_dark"], collection=collection)
    add_box("StoveTop", (x, y, 0.85), (1.7, 1.1, 0.1),
            material=MATS["stone"], collection=collection)
    add_box("StoveChimney", (x + 0.5, y + 0.3, 2.4), (0.5, 0.5, 3.0),
            material=MATS["stone_dark"], collection=collection)
    add_box("StoveHole", (x - 0.2, y - 0.45, 0.3), (0.5, 0.05, 0.4),
            material=MATS["ember"], collection=collection)
    add_cylinder("StovePot", (x - 0.2, y, 1.05), 0.25, 0.3,
                 material=MATS["copper"], collection=collection, vertices=16)
    add_cylinder("StovePotLid", (x - 0.2, y, 1.22), 0.28, 0.05,
                 material=MATS["bronze"], collection=collection, vertices=16)


def build_hanging_pots(collection, x, y):
    add_box("HangingRackBar", (x, y, 2.0), (1.8, 0.06, 0.06),
            material=MATS["iron"], collection=collection)
    for i, dx in enumerate([-0.7, -0.2, 0.3, 0.8]):
        add_cylinder(f"HangingChain_{i}", (x + dx, y, 1.85),
                     0.015, 0.25,
                     material=MATS["iron"], collection=collection, vertices=6)
        add_cylinder(f"HangingPot_{i}", (x + dx, y, 1.6),
                     0.12 - i * 0.01, 0.2 - i * 0.02,
                     material=MATS["bronze"], collection=collection,
                     vertices=12)


def build_herb_bundles(collection, x, y):
    for i in range(4):
        dx = (i - 1.5) * 0.35
        add_cylinder(f"HerbBundle_{i}", (x + dx, y, 1.7),
                     0.08, 0.35,
                     material=MATS["leaf_dark"],
                     collection=collection, vertices=8)
        add_cylinder(f"HerbTie_{i}", (x + dx, y, 1.55),
                     0.09, 0.03,
                     material=MATS["fabric_brown"],
                     collection=collection, vertices=8)


def build_kitchen(collection):
    build_barrel(collection, "BarrelA", 2.8, -4.8)
    build_barrel(collection, "BarrelB", 3.6, -4.8)
    build_barrel(collection, "BarrelC", 5.7, -4.5)
    build_barrel(collection, "BarrelD", 5.7, -3.8)
    build_cauldron(collection)
    build_sacks(collection)
    build_kitchen_shelf(collection)
    build_kitchen_stove(collection, 5.5, -2.9)
    build_hanging_pots(collection, 4.5, -4.5)
    build_herb_bundles(collection, 5.5, -4.0)


# ================================================================
# FIREPLACE
# ================================================================
def build_fireplace(collection):
    x, y = 3.5, 5.5
    add_box("FireplaceMantel", (x, y, 2.4), (2.4, 0.6, 0.3),
            material=MATS["stone_dark"], collection=collection)
    for side, dx in [("L", -0.9), ("R", 0.9)]:
        add_box(f"FireplaceSide_{side}", (x + dx, y, 1.2),
                (0.4, 0.5, 2.4),
                material=MATS["stone"], collection=collection)
    add_box("FireplaceBack", (x, y + 0.2, 1.2), (2.0, 0.2, 2.4),
            material=MATS["stone_dark"], collection=collection)
    add_sphere("FireplaceFire", (x, y - 0.1, 0.4), 0.4,
               material=MATS["fire"], collection=collection,
               segments=16, rings=12)
    add_sphere("FireplaceEmber", (x, y - 0.1, 0.15), 0.3,
               material=MATS["ember"], collection=collection,
               segments=12, rings=8)
    for i, (dx, dz) in enumerate([(-0.3, 0.15), (0.1, 0.15), (0.35, 0.2)]):
        add_cylinder(f"FireplaceLog_{i}", (x + dx, y - 0.05, dz),
                     0.08, 0.6,
                     material=MATS["wood_dark"], collection=collection,
                     vertices=8, rotation=(0, math.pi / 2, 0))


# ================================================================
# WINDOWS
# ================================================================
def build_window(collection, name, x, y, wall_side):
    if wall_side == "left":
        add_box(f"{name}_Frame", (x, y, 4.5), (0.5, 1.2, 1.6),
                material=MATS["stone_dark"], collection=collection)
        add_box(f"{name}_Glass", (x + 0.05, y, 4.5), (0.1, 1.0, 1.4),
                material=MATS["window_light"], collection=collection)
    else:
        add_box(f"{name}_Frame", (x, y, 4.5), (0.5, 1.2, 1.6),
                material=MATS["stone_dark"], collection=collection)
        add_box(f"{name}_Glass", (x - 0.05, y, 4.5), (0.1, 1.0, 1.4),
                material=MATS["window_light"], collection=collection)


def build_windows(collection):
    h = CASTLE_HALF
    for i, y in enumerate([-3.0, 0.0, 3.0]):
        build_window(collection, f"WinL_{i}", -h, y, "left")
        build_window(collection, f"WinR_{i}", h, y, "right")


def build_stained_glass_window(collection, name, x, y, wall_side):
    glass_mats = [MATS["glass_red"], MATS["glass_blue"],
                  MATS["glass_green"], MATS["glass_yellow"]]
    add_box(f"{name}_Frame", (x, y - 0.4, 4.5), (1.4, 0.4, 2.0),
            material=MATS["stone_dark"], collection=collection)
    for i in range(2):
        for j in range(3):
            px = x - 0.3 + i * 0.6
            pz = 3.7 + j * 0.55
            mat = glass_mats[(i * 3 + j) % len(glass_mats)]
            add_box(f"{name}_Pane_{i}_{j}", (px, y - 0.45, pz),
                    (0.5, 0.05, 0.45),
                    material=mat, collection=collection)
    add_box(f"{name}_MullionV", (x, y - 0.5, 4.5),
            (0.08, 0.08, 1.9),
            material=MATS["stone_dark"], collection=collection)
    add_box(f"{name}_MullionH", (x, y - 0.5, 4.5),
            (1.2, 0.08, 0.08),
            material=MATS["stone_dark"], collection=collection)


# ================================================================
# CHAPEL
# ================================================================
def build_chapel(collection):
    cx, cy = 4.5, 4.5
    add_box("AltarStep", (cx, cy, 0.1), (2.4, 1.2, 0.2),
            material=MATS["stone_light"], collection=collection)
    add_box("AltarBody", (cx, cy, 0.5), (1.8, 0.8, 0.8),
            material=MATS["stone"], collection=collection)
    add_box("AltarTop", (cx, cy, 0.95), (2.0, 0.9, 0.1),
            material=MATS["stone_light"], collection=collection)
    add_box("AltarCrossV", (cx, cy, 1.35), (0.08, 0.08, 0.7),
            material=MATS["gold"], collection=collection)
    add_box("AltarCrossH", (cx, cy, 1.5), (0.35, 0.08, 0.08),
            material=MATS["gold"], collection=collection)
    for i, dx in enumerate([-0.5, 0.5]):
        add_cylinder(f"AltarCandle_{i}", (cx + dx, cy, 1.1),
                     0.04, 0.3,
                     material=MATS["fabric_cream"],
                     collection=collection, vertices=8)
        add_sphere(f"AltarCandleFlame_{i}", (cx + dx, cy, 1.3),
                   0.05, material=MATS["candle"],
                   collection=collection, segments=8, rings=6)
    for i, dy in enumerate([-1.0, -1.5]):
        px = cx
        py = cy + dy - 1.5
        add_box(f"PewSeat_{i}", (px, py, 0.45),
                (1.8, 0.35, 0.08),
                material=MATS["wood"], collection=collection)
        add_box(f"PewBack_{i}", (px, py + 0.15, 0.75),
                (1.8, 0.08, 0.6),
                material=MATS["wood"], collection=collection)
        for j, dx in enumerate([-0.75, 0.75]):
            add_box(f"PewLeg_{i}_{j}", (px + dx, py, 0.22),
                    (0.08, 0.35, 0.45),
                    material=MATS["wood_dark"], collection=collection)
    build_rug(collection, "ChapelRug", (cx, cy - 1.2, 0.06),
              (1.8, 2.5), MATS["fabric_purple"])


# ================================================================
# TREASURE ROOM
# ================================================================
def build_treasure_room(collection):
    x, y = -4.5, 3.0
    build_chest(collection, "TreasureChestA", x, y, rotation=0)
    build_chest(collection, "TreasureChestB", x + 1.0, y + 0.3,
                rotation=math.radians(15))
    build_chest(collection, "TreasureChestC", x - 0.4, y + 1.0,
                rotation=math.radians(-10))
    for i, (px, py) in enumerate([
        (x + 0.5, y - 0.5), (x - 0.5, y + 0.5), (x + 0.2, y + 0.7),
    ]):
        for j in range(6):
            rng = random.Random(i * 10 + j)
            ox = rng.uniform(-0.15, 0.15)
            oy = rng.uniform(-0.15, 0.15)
            oz = rng.uniform(0.05, 0.15)
            add_cylinder(f"Coin_{i}_{j}", (px + ox, py + oy, oz),
                         0.05, 0.02,
                         material=MATS["gold"],
                         collection=collection, vertices=8)
    add_torus("CrownBase", (x, y - 0.1, 0.75), 0.12, 0.02,
              material=MATS["gold"], collection=collection)
    for i in range(4):
        angle = 2 * math.pi * i / 4
        dx = math.cos(angle) * 0.1
        dy = math.sin(angle) * 0.1
        add_cone(f"CrownSpike_{i}", (x + dx, y - 0.1 + dy, 0.85),
                 0.03, 0.0, 0.1,
                 material=MATS["gold"],
                 collection=collection, vertices=6)
    add_sphere("CrownJewel", (x, y - 0.1, 0.72), 0.04,
               material=MATS["gem_ruby"], collection=collection,
               segments=8, rings=6)


# ================================================================
# WEAPON RACK
# ================================================================
def build_weapon_rack(collection, x, y):
    add_box("WeaponRackBack", (x, y + 0.2, 1.5),
            (2.4, 0.1, 2.4),
            material=MATS["wood_dark"], collection=collection)
    for z in [0.5, 2.5]:
        add_box(f"WeaponRackRail_{z}", (x, y, z),
                (2.4, 0.15, 0.1),
                material=MATS["wood"], collection=collection)
    for i, dx in enumerate([-0.8, -0.4, 0.0]):
        add_box(f"SwordBlade_{i}", (x + dx, y - 0.1, 1.6),
                (0.06, 0.06, 1.6),
                material=MATS["steel"], collection=collection)
        add_box(f"SwordHilt_{i}", (x + dx, y - 0.1, 0.85),
                (0.15, 0.1, 0.15),
                material=MATS["gold"], collection=collection)
    for i, dx in enumerate([0.5, 0.9]):
        add_box(f"SpearShaft_{i}", (x + dx, y - 0.1, 1.5),
                (0.05, 0.05, 2.4),
                material=MATS["wood"], collection=collection)
        add_cone(f"SpearTip_{i}", (x + dx, y - 0.1, 2.85),
                 0.06, 0.0, 0.3,
                 material=MATS["steel"],
                 collection=collection, vertices=6)
    add_box("WallShield", (x - 1.2, y - 0.05, 1.5),
            (0.6, 0.1, 0.8),
            material=MATS["steel"], collection=collection)
    add_box("WallShieldStripe", (x - 1.2, y - 0.1, 1.5),
            (0.15, 0.05, 0.7),
            material=MATS["fabric_red"], collection=collection)
    add_sphere("WallShieldBoss", (x - 1.2, y - 0.1, 1.5), 0.1,
               material=MATS["gold"], collection=collection,
               segments=12, rings=8)


# ================================================================
# TRAPDOOR
# ================================================================
def build_trapdoor(collection, x, y):
    add_box("TrapdoorFrame", (x, y, 0.15), (1.6, 1.6, 0.1),
            material=MATS["stone_dark"], collection=collection)
    add_box("TrapdoorHatch", (x, y, 0.22), (1.4, 1.4, 0.06),
            material=MATS["wood_dark"], collection=collection)
    add_box("TrapdoorHandle", (x + 0.5, y, 0.28), (0.15, 0.05, 0.05),
            material=MATS["iron"], collection=collection)
    for dx in [-0.5, 0.5]:
        add_box(f"TrapdoorHinge_{dx}", (x + dx, y - 0.65, 0.25),
                (0.15, 0.1, 0.04),
                material=MATS["iron"], collection=collection)


# ================================================================
# DECORATIONS
# ================================================================
def build_throne_room_decorations(collection):
    build_banner(collection, "BannerBack_C", 0.0, CASTLE_HALF - 0.35,
                 5.0, "south", MATS["fabric_red"])
    build_banner(collection, "BannerBack_L", -3.0, CASTLE_HALF - 0.35,
                 5.0, "south", MATS["fabric_red"])
    build_banner(collection, "BannerBack_R", 3.0, CASTLE_HALF - 0.35,
                 5.0, "south", MATS["fabric_red"])
    for i, x in enumerate([-5.8, -3.5, 3.5, 5.8]):
        build_torch(collection, f"Torch_Back_{i}", x, CASTLE_HALF - 0.35,
                    3.0, "north")
    for i, y in enumerate([-1.0, 2.0]):
        build_torch(collection, f"Torch_Left_{i}", -CASTLE_HALF + 0.35, y,
                    3.0, "left")
        build_torch(collection, f"Torch_Right_{i}", CASTLE_HALF - 0.35, y,
                    3.0, "right")
    build_candelabra(collection, "ThroneCandelabra_L", -1.5, 5.5, z=0.6)
    build_candelabra(collection, "ThroneCandelabra_R", 1.5, 5.5, z=0.6)
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


def build_point_light(collection, name, x, y, z, energy=80,
                       color=(1, 0.75, 0.4)):
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
    build_point_light(collection, "L_Chapel", 4.5, 4.5, 2.0, 40, (1, 0.85, 0.6))
    build_point_light(collection, "L_Treasure", -4.5, 3.0, 1.5, 30, (1, 0.9, 0.5))


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
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        use_selection=False,
        export_cameras=True,
        export_lights=True,
        export_apply=True,
        export_yup=True,
        export_materials='EXPORT',
    )


def compute_output_path():
    try:
        blend_dir = pathlib.Path(bpy.data.filepath).parent
        if str(blend_dir) == "" or str(blend_dir) == ".":
            blend_dir = pathlib.Path.cwd()
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

    clear_scene()
    build_all_materials()

    # Collections
    coll_ground    = create_collection("Ground")
    coll_outdoor   = create_collection("Outdoor")
    coll_moat      = create_collection("Moat")
    coll_struct    = create_collection("Structure")
    coll_towers    = create_collection("Towers")
    coll_floor     = create_collection("FloorAndWalls")
    coll_furniture = create_collection("Furniture")
    coll_decor     = create_collection("Decorations")
    coll_light     = create_collection("Lighting")
    coll_cam       = create_collection("Cameras")

    # Outdoor
    build_ground(coll_ground)
    build_moat(coll_moat)
    build_drawbridge(coll_outdoor)
    build_stairs(coll_outdoor)
    build_trees(coll_outdoor)
    build_bushes(coll_outdoor)
    build_flowers(coll_outdoor)
    build_well(coll_outdoor, 10.0, -3.0)
    build_horse_trough(coll_outdoor, -9.0, -3.0)
    build_fountain(coll_outdoor, -10.5, 6.0)
    build_statue(coll_outdoor, 10.5, 6.0)
    build_benches(coll_outdoor)
    build_lamps(coll_outdoor)
    build_carts(coll_outdoor)
    build_stables(coll_outdoor, 12.5, -11.0)
    build_horse(coll_outdoor, 12.5, -11.0)
    build_catapults(coll_outdoor)

    # Structure
    build_back_wall(coll_struct)
    build_left_wall(coll_struct)
    build_right_wall(coll_struct)
    build_front_wall(coll_struct)
    build_gate(coll_struct)

    # Towers
    build_tower("TowerBL", -CASTLE_HALF, -CASTLE_HALF, coll_towers)
    build_tower("TowerBR",  CASTLE_HALF, -CASTLE_HALF, coll_towers)
    build_tower("TowerTL", -CASTLE_HALF,  CASTLE_HALF, coll_towers)
    build_tower("TowerTR",  CASTLE_HALF,  CASTLE_HALF, coll_towers)

    # Floors, partitions, windows
    build_floor(coll_floor)
    build_partition_walls(coll_floor)
    build_windows(coll_struct)
    build_stained_glass_window(coll_struct, "StainedWin1",
                                0.0, CASTLE_HALF, "back")

    # Throne room
    build_dais(coll_furniture)
    build_throne(coll_furniture)
    build_long_table(coll_furniture)
    build_chairs_around_table(coll_furniture)
    build_chandelier(coll_decor)
    build_fireplace(coll_furniture)

    # Rooms
    build_bedroom(coll_furniture)
    build_library(coll_furniture)
    build_kitchen(coll_furniture)
    build_chapel(coll_furniture)
    build_treasure_room(coll_decor)
    build_weapon_rack(coll_decor, -3.5, -5.4)
    build_armor_stand(coll_decor)
    build_trapdoor(coll_floor, 3.0, 2.5)

    # Decorations
    build_throne_room_decorations(coll_decor)

    # Lighting & camera
    build_lights(coll_light)
    build_camera(coll_cam)

    # ⚠️ CRITICAL: ensure every mesh has a colored material
    ensure_all_objects_have_materials()

    # ⚠️ CRITICAL: disconnect procedural nodes so glTF gets solid colors
    prepare_materials_for_gltf()

    # Report
    report_materials_summary()

    # Export
    out_path = compute_output_path()
    export_glb(str(out_path))
    print(f"✅ Exported: {out_path}")
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