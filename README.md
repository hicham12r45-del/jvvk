# jvvk

Minimal Blender scene with a cube, light, and camera

A Blender 3D project created with **Motion Studio**.

## Render

The render runs on GitHub Actions via `.github/workflows/blender-render.yml`.
Blender executes `main.py` in background mode and exports a GLB file
to `out/model.glb`, which is uploaded as an artifact named `model`.

## Local preview

```bash
blender --background --python main.py
```