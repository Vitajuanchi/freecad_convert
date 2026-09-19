"""
Arma el MP4 a partir de la secuencia de PNG que dejo studio_animation.py.

Uso:
    blender --background --python encode_video.py -- --frames render --out metegol.mp4 --fps 25
"""

import argparse
import glob
import os
import sys

import bpy


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--frames", default="render", help="carpeta con los PNG")
    p.add_argument("--pattern", default="frame_*.png")
    p.add_argument("--out", default="metegol_10s.mp4")
    p.add_argument("--fps", type=int, default=25)
    return p.parse_args(argv)


def strip_collection(scene):
    """Blender renombro 'sequences' a 'strips' en 4.4; soportamos las dos."""
    editor = scene.sequence_editor
    return getattr(editor, "strips", None) or editor.sequences


def main():
    args = parse_args()
    folder = os.path.abspath(args.frames)
    files = sorted(glob.glob(os.path.join(folder, args.pattern)))
    if not files:
        raise SystemExit(f"ERROR: no hay PNG que coincidan con "
                         f"{args.pattern} en {folder}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    probe = bpy.data.images.load(files[0])
    width, height = probe.size
    bpy.data.images.remove(probe)

    scene.sequence_editor_create()
    strips = strip_collection(scene)
    strip = strips.new_image(name="frames", filepath=files[0],
                             channel=1, frame_start=1)
    for path in files[1:]:
        strip.elements.append(os.path.basename(path))

    scene.frame_start = 1
    scene.frame_end = len(files)
    scene.render.fps = args.fps
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100

    # los PNG ya vienen con el transform aplicado: no lo pisamos de nuevo
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"

    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.gopsize = args.fps
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = os.path.abspath(args.out)

    bpy.ops.render.render(animation=True)
    print(f"[video] {len(files)} frames -> {args.out} "
          f"({width}x{height} @ {args.fps} fps, "
          f"{len(files) / args.fps:.1f} s)")


if __name__ == "__main__":
    main()
