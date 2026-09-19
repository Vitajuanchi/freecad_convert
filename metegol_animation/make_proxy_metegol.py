"""
Metegol de prueba (proxy) para validar escenario, encuadre e iluminacion
sin el modelo real.

Uso:
    blender --background --python make_proxy_metegol.py -- --out proxy.blend
"""

import argparse
import sys

import bpy


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="proxy_metegol.blend")
    return p.parse_args(argv)


def wipe():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, colour, roughness=0.45, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def box(name, size, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj


def cylinder(name, radius, depth, location, rotation, mat):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=depth, location=location, rotation=rotation,
        vertices=32)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def build():
    wood = material("madera", (0.28, 0.16, 0.09), roughness=0.38)
    felt = material("pano", (0.05, 0.28, 0.12), roughness=0.85)
    steel = material("acero", (0.78, 0.78, 0.80), roughness=0.22, metallic=1.0)
    red = material("jugador_rojo", (0.62, 0.07, 0.08), roughness=0.35)
    blue = material("jugador_azul", (0.06, 0.16, 0.55), roughness=0.35)
    black = material("goma", (0.04, 0.04, 0.05), roughness=0.55)

    length, width, top_h = 1.40, 0.76, 0.88

    # patas
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("pata", (0.07, 0.07, top_h - 0.20),
                (sx * (length / 2 - 0.08), sy * (width / 2 - 0.08),
                 (top_h - 0.20) / 2), wood)

    # cuerpo de la mesa
    box("gabinete", (length, width, 0.20), (0, 0, top_h - 0.10), wood)
    # cancha hundida
    box("cancha", (length - 0.12, width - 0.12, 0.02),
        (0, 0, top_h - 0.035), felt)

    # barras con jugadores
    rod_z = top_h + 0.035
    layout = [(-0.52, red), (-0.26, blue), (0.0, red), (0.26, blue), (0.52, red)]
    for (x, colour) in layout:
        cylinder("barra", 0.012, width + 0.42, (x, 0, rod_z),
                 (1.5707963, 0, 0), steel)
        for sy in (-1, 1):
            cylinder("mango", 0.028, 0.11,
                     (x, sy * (width / 2 + 0.16), rod_z),
                     (1.5707963, 0, 0), black)
        for y in (-0.19, 0.0, 0.19):
            box("jugador", (0.05, 0.035, 0.115), (x, y, rod_z - 0.045), colour)

    # pelota
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.017, location=(0.18, -0.1, top_h - 0.008))
    ball = bpy.context.object
    ball.name = "pelota"
    ball.data.materials.append(material("pelota", (0.92, 0.88, 0.30), roughness=0.3))
    bpy.ops.object.shade_smooth()


def main():
    args = parse_args()
    wipe()
    build()
    bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(args.out))
    print(f"[proxy] guardado en {args.out}")


if __name__ == "__main__":
    main()
