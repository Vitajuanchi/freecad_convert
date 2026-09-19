"""
Escenario editorial de fondo blanco + animacion de 10 s para el metegol.

Uso:
    blender metegol.blend --background --python studio_animation.py -- [opciones]

Opciones:
    --out RUTA        carpeta de salida de los frames PNG (default ./render)
    --duration SEG    duracion en segundos (default 10)
    --fps N           cuadros por segundo (default 25)
    --res WxH         resolucion (default 1920x1080)
    --samples N       samples de Cycles (default 64)
    --size M          tamano al que se normaliza el metegol, en metros (default 2.2)
    --exposure EV     correccion de exposicion en pasos (default 0)
    --test            render rapido de 5 frames sueltos a media resolucion
    --save-blend RUTA guarda el .blend con escenario y keyframes ya armados
    --no-dof          desactiva la profundidad de campo
    --no-render       arma todo pero no renderiza

El escenario es un ciclorama cerrado de 360 grados, asi que la camara puede
dar la vuelta completa sin que aparezca el borde del fondo.
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

STUDIO_PREFIX = "STUDIO_"
SUBJECT_ROOT = "METEGOL_ROOT"
GEOMETRY_TYPES = {"MESH", "CURVE", "SURFACE", "FONT", "META"}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []

    p = argparse.ArgumentParser()
    p.add_argument("--out", default="render")
    p.add_argument("--duration", type=float, default=10.0)
    p.add_argument("--fps", type=int, default=25)
    p.add_argument("--res", default="1920x1080")
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--size", type=float, default=2.2)
    p.add_argument("--exposure", type=float, default=0.0)
    p.add_argument("--test", action="store_true")
    p.add_argument("--save-blend", default="")
    p.add_argument("--no-dof", action="store_true")
    p.add_argument("--no-render", action="store_true")
    return p.parse_args(argv)


# --------------------------------------------------------------------------
# el metegol: deteccion, agrupado, centrado y escala
# --------------------------------------------------------------------------
def is_subject(obj):
    if obj.type in GEOMETRY_TYPES:
        return True
    return obj.type == "EMPTY" and obj.instance_collection is not None


def purge_cameras_and_lights():
    """El escenario aporta su propia camara e iluminacion."""
    for obj in [o for o in bpy.data.objects if o.type in {"CAMERA", "LIGHT"}]:
        bpy.data.objects.remove(obj, do_unlink=True)


def world_bounds(skip_prefix=None):
    """Bounding box en el mundo, evaluando modificadores e instancias."""
    deps = bpy.context.evaluated_depsgraph_get()
    lo = Vector((float("inf"),) * 3)
    hi = Vector((float("-inf"),) * 3)
    found = False

    for inst in deps.object_instances:
        obj = inst.object
        if obj.type not in GEOMETRY_TYPES:
            continue
        if skip_prefix and obj.name.startswith(skip_prefix):
            continue
        mat = inst.matrix_world
        for corner in obj.bound_box:
            p = mat @ Vector(corner)
            lo.x, lo.y, lo.z = min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)
            hi.x, hi.y, hi.z = max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)
            found = True

    return (lo, hi) if found else (None, None)


def normalize_subject(target_size):
    tops = [o for o in bpy.data.objects if is_subject(o) and o.parent is None]
    if not tops:
        raise SystemExit(
            "ERROR: no hay geometria en este .blend. Corrleo sobre el archivo "
            "del metegol, no sobre uno vacio."
        )

    root = bpy.data.objects.new(SUBJECT_ROOT, None)
    root.empty_display_type = "PLAIN_AXES"
    bpy.context.scene.collection.objects.link(root)

    for obj in tops:
        matrix = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = matrix
    bpy.context.view_layer.update()

    lo, hi = world_bounds()
    if lo is None:
        raise SystemExit("ERROR: la geometria no tiene volumen medible.")

    longest = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
    if longest > 1e-6:
        root.scale = (target_size / longest,) * 3
    bpy.context.view_layer.update()

    lo, hi = world_bounds()
    centre = (lo + hi) * 0.5
    root.location = (
        root.location.x - centre.x,
        root.location.y - centre.y,
        root.location.z - lo.z,          # queda apoyado sobre el piso
    )
    bpy.context.view_layer.update()

    lo, hi = world_bounds()
    print(f"[metegol] dimensiones normalizadas: "
          f"{hi.x - lo.x:.2f} x {hi.y - lo.y:.2f} x {hi.z - lo.z:.2f} m")
    return root, lo, hi


# --------------------------------------------------------------------------
# ciclorama cerrado: piso, empalme curvo y pared, revolucionados 360 grados
# --------------------------------------------------------------------------
def build_cyclorama(scale):
    import bmesh

    floor_r = 3.2 * scale          # piso plano hasta aca
    fillet_r = 1.8 * scale         # radio del empalme piso-pared
    wall_top = 9.0 * scale
    segments = 96

    # perfil (radio, altura), de adentro hacia afuera y hacia arriba
    profile = []
    rings = 6
    for i in range(1, rings + 1):
        profile.append((floor_r * i / rings, 0.0))

    arc_steps = 20
    cr, cz = floor_r, fillet_r     # centro del arco de empalme
    for i in range(1, arc_steps + 1):
        a = -math.pi / 2 + (math.pi / 2) * (i / arc_steps)
        profile.append((cr + fillet_r * math.cos(a), cz + fillet_r * math.sin(a)))

    wall_r = floor_r + fillet_r
    wall_steps = 6
    for i in range(1, wall_steps + 1):
        profile.append((wall_r, fillet_r + (wall_top - fillet_r) * i / wall_steps))

    mesh = bpy.data.meshes.new(STUDIO_PREFIX + "cyclorama_mesh")
    bm = bmesh.new()

    centre_vert = bm.verts.new((0.0, 0.0, 0.0))
    rings_verts = []
    for (r, z) in profile:
        ring = []
        for s in range(segments):
            a = 2.0 * math.pi * s / segments
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings_verts.append(ring)
    bm.verts.ensure_lookup_table()

    # abanico central
    first = rings_verts[0]
    for s in range(segments):
        bm.faces.new((centre_vert, first[s], first[(s + 1) % segments]))
    # anillos
    for i in range(len(rings_verts) - 1):
        a_ring, b_ring = rings_verts[i], rings_verts[i + 1]
        for s in range(segments):
            t = (s + 1) % segments
            bm.faces.new((a_ring[s], b_ring[s], b_ring[t], a_ring[t]))

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(STUDIO_PREFIX + "cyclorama", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for poly in mesh.polygons:
        poly.use_smooth = True

    mat = bpy.data.materials.new(STUDIO_PREFIX + "blanco")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.90, 0.90, 0.91, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.65
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    obj.data.materials.append(mat)
    return obj


# --------------------------------------------------------------------------
# iluminacion editorial
# --------------------------------------------------------------------------
def make_empty(name, location):
    obj = bpy.data.objects.new(STUDIO_PREFIX + name, None)
    obj.empty_display_type = "SPHERE"
    obj.empty_display_size = 0.2
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    return obj


def add_area_light(name, location, size, power, target):
    data = bpy.data.lights.new(STUDIO_PREFIX + name, type="AREA")
    data.energy = power
    data.shape = "SQUARE"
    data.size = size

    obj = bpy.data.objects.new(STUDIO_PREFIX + name, data)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)

    con = obj.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    return obj


def build_lighting(centre, height, scale):
    """Esquema de producto: key suave, fill amplio, rim de separacion y cenital.

    Todo se posiciona en multiplos del tamano del sujeto, asi el esquema
    sigue funcionando con cualquier modelo.
    """
    s = scale
    aim = make_empty("aim_sujeto", centre)

    add_area_light("key",  (-1.9 * s, -2.1 * s, 2.4 * s), size=2.3 * s,
                   power=105 * s * s, target=aim)
    add_area_light("fill", (2.3 * s, -1.6 * s, 1.2 * s), size=2.7 * s,
                   power=22 * s * s, target=aim)
    add_area_light("rim",  (1.4 * s, 1.7 * s, 2.0 * s), size=1.1 * s,
                   power=54 * s * s, target=aim)
    add_area_light("top",  (0.0, -0.2 * s, 2.9 * s), size=3.2 * s,
                   power=34 * s * s, target=aim)

    # el ciclorama se levanta a blanco con el ambiente, no con focos directos:
    # asi no aparecen manchas de luz sobre el fondo
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bg.inputs["Strength"].default_value = 0.78
    return aim


# --------------------------------------------------------------------------
# camara: orbita completa con encuadre calculado
# --------------------------------------------------------------------------
# (t, giro_orbita_grados, altura / alto_del_sujeto, encuadre, lente_mm)
CAMERA_BEATS = [
    (0.00, -40.0, 1.80, 0.68, 45.0),   # apertura alta, se ve toda la cancha
    (0.25,  15.0, 1.38, 0.80, 52.0),   # se acerca y baja el punto de vista
    (0.50, 115.0, 1.22, 0.88, 58.0),   # perfil, camara baja
    (0.75, 225.0, 1.55, 0.72, 55.0),   # sube y abre por detras
    (1.00, 320.0, 1.40, 0.82, 62.0),   # cierra en el plano heroe
]


def frame_fill(cam_eval, corners):
    """Cuanto del encuadre ocupa el sujeto: 1.0 = justo tocando el borde."""
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    worst = 0.0
    for c in corners:
        uvw = world_to_camera_view(scene, cam_eval, c)
        if uvw.z <= 1e-4:            # algun vertice quedo detras de la camara
            return None
        worst = max(worst, abs(uvw.x - 0.5) * 2.0, abs(uvw.y - 0.5) * 2.0)
    return worst


def solve_distance(cam, rig, corners, spin, cam_z, centre_z, lens, fill, seed):
    """Busca la distancia a la que el sujeto ocupa la fraccion pedida del cuadro."""
    cam.data.lens = lens
    rig.rotation_euler = (0.0, 0.0, math.radians(spin))

    d = seed
    for _ in range(14):
        cam.location = (0.0, -d, cam_z - centre_z)
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        current = frame_fill(cam.evaluated_get(deps), corners)
        if current is None or current < 1e-6:
            d *= 1.7
            continue
        if abs(current - fill) < 0.002:
            break
        d *= current / fill
    return d


def build_camera(aim, centre, lo, hi, total_frames, use_dof):
    scene = bpy.context.scene
    centre_v = Vector(centre)
    height = hi.z - lo.z
    radius = (hi - lo).length * 0.5

    corners = [Vector((x, y, z))
               for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]

    rig = bpy.data.objects.new(STUDIO_PREFIX + "cam_rig", None)
    rig.empty_display_type = "CIRCLE"
    rig.empty_display_size = 1.0
    rig.location = centre_v
    scene.collection.objects.link(rig)

    data = bpy.data.cameras.new(STUDIO_PREFIX + "camara")
    data.sensor_width = 36.0
    data.lens = 50.0
    data.clip_start = 0.01
    data.clip_end = 500.0
    if use_dof:
        data.dof.use_dof = True
        data.dof.focus_object = aim
        data.dof.aperture_fstop = 6.3

    cam = bpy.data.objects.new(STUDIO_PREFIX + "camara", data)
    scene.collection.objects.link(cam)
    cam.parent = rig

    con = cam.constraints.new("TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    scene.camera = cam

    seed = radius * 3.0
    for (t, spin, h_factor, fill, lens) in CAMERA_BEATS:
        frame = 1 + round(t * (total_frames - 1))
        cam_z = lo.z + height * h_factor

        dist = solve_distance(cam, rig, corners, spin, cam_z,
                              centre_v.z, lens, fill, seed)
        seed = dist

        rig.rotation_euler = (0.0, 0.0, math.radians(spin))
        rig.keyframe_insert("rotation_euler", frame=frame)

        cam.location = (0.0, -dist, cam_z - centre_v.z)
        cam.keyframe_insert("location", frame=frame)

        data.lens = lens
        data.keyframe_insert("lens", frame=frame)

        print(f"[camara] f{frame:>4}  giro {spin:>7.1f}deg  "
              f"dist {dist:>5.2f} m  altura {cam_z:>5.2f} m  lente {lens:.0f} mm")

    for holder in (rig, cam, data):
        smooth_fcurves(holder)
    return cam, rig


def smooth_fcurves(holder):
    """Bezier con handles automaticos: arranque y frenado suaves, sin tirones."""
    anim = holder.animation_data
    if not anim or not anim.action:
        return
    for fcurve in anim.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"
        if len(fcurve.keyframe_points) >= 2:
            fcurve.keyframe_points[0].easing = "EASE_IN_OUT"
            fcurve.keyframe_points[-1].easing = "EASE_IN_OUT"
        fcurve.update()


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------
def configure_render(args, total_frames):
    scene = bpy.context.scene
    width, _, height = args.res.partition("x")

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.05
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 6
    scene.cycles.transparent_max_bounces = 6
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False

    scene.render.resolution_x = int(width)
    scene.render.resolution_y = int(height)
    scene.render.resolution_percentage = 100
    scene.render.use_persistent_data = True     # acelera mucho la animacion en CPU
    scene.render.fps = args.fps
    scene.frame_start = 1
    scene.frame_end = total_frames

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15
    scene.render.filepath = os.path.join(os.path.abspath(args.out), "frame_")

    # blanco limpio, sin el lavado de AgX
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = args.exposure


def main():
    args = parse_args()
    total_frames = max(2, round(args.duration * args.fps))

    purge_cameras_and_lights()
    _, lo, hi = normalize_subject(args.size)

    centre = ((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5, (lo.z + hi.z) * 0.5)
    height = hi.z - lo.z
    scale = max(hi.x - lo.x, hi.y - lo.y, height)

    build_cyclorama(scale)
    aim = build_lighting(centre, height, scale)

    configure_render(args, total_frames)          # antes de encuadrar: define el aspecto
    build_camera(aim, centre, lo, hi, total_frames, use_dof=not args.no_dof)

    if args.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save_blend))
        print(f"[metegol] escenario guardado en {args.save_blend}")

    if args.no_render:
        return

    os.makedirs(os.path.abspath(args.out), exist_ok=True)

    if args.test:
        scene = bpy.context.scene
        scene.render.resolution_percentage = 50
        scene.cycles.samples = max(16, args.samples // 4)
        for (t, *_rest) in CAMERA_BEATS:
            frame = 1 + round(t * (total_frames - 1))
            scene.frame_set(frame)
            scene.render.filepath = os.path.join(
                os.path.abspath(args.out), f"test_{frame:04d}")
            bpy.ops.render.render(write_still=True)
        return

    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
