# Design Files

3D models, laser cutting templates, and other fabrication files.

## Subfolders

### `3d_models/`
3D printable parts and assemblies.
- Camera mounts, block prototypes, table brackets
- Preferred formats: `.stl`, `.step`, `.3mf`
- Include source files (Fusion 360 / SolidWorks / FreeCAD) when possible

### `laser_cut/`
Laser cutting files for acrylic and other sheet materials.
- Grid constraint layer templates
- Table top panels
- Preferred formats: `.dxf`, `.svg`, `.ai`
- Always include a dimensioned PDF for reference

## Naming Convention

```
<part_name>_<version>_<material>.<ext>
Example: grid_plate_v2_acrylic5mm.dxf
```
