# samplecraft — samples as exact geometry

samplecraft describes a sample for neutron (or X-ray) imaging and scattering the way Monte Carlo transport codes
(MCNP, OpenMC, Geant4) describe their cells: a **tree of bodies**, each of one material, each inside its parent, no two
bodies of the same parent overlapping. What a ray crosses in each material is computed **exactly** (intervals of
each shape along the ray; a child replaces its parent's material on its part). The ODIN twin uses it for its
hybrid model (thickness maps, transmission); the sample builder (`../Sample_builder.ipynb`, `../scene_builder.py`)
edits its recipes without code.

```python
import samplecraft as sc
scene = sc.Scene.load("my_sample.yml")        # components expanded, fills generated (from the seed)
scene.check()                                  # [] if every body is inside its parent and no siblings overlap
L = scene.material_lengths(o, d)               # {material: path length [mm]} along rays o + t d
T = scene.transmission(o, d, wavelength_A=3)   # exp(−Σ Σ_m L_m), NCrystal cross-sections
scene.volumes()                                # {material: volume [mm³]}
scene.save("built.yml")                        # the scene as built, with its recipe
```

## A scene file (YAML; lengths in mm, angles in degrees)

```yaml
samplecraft: 1
name: Machined steel part
seed: 7                                        # the same file gives the same sample
provenance: {sources: [...], assumptions: [...]}
materials:
  steel: {ncrystal: Fe_sg229_Iron-alpha.ncmat}
  rock:  {minerals: {plag: 60, cpx: 40}}       # MINERALS of materials.py, by volume
  oxide: {formula: Fe2O3, density: 5.26}
  water: {ncrystal: "stdlib::LiquidWaterH2O_T293.6K.ncmat"}
  wet:   {mix: {rock: 0.8, water: 0.2}}        # other materials of the scene, by volume
  hrich: {calibrate: {base: {minerals: {magh: 65, ilm: 20, plag: 15}}, add: water, sigma_cm: 1.9, wavelength_A: 1.8},
          source: "Naver et al. 2026, Table S2"}
  porous: {ncrystal: Al_sg225.ncmat, density_factor: 0.9}
components:                                    # bodies used several times
  clast: {material: rock, shape: {type: blob, size: [0.3, 0.4, 0.3], wobble: 0.12, seed: 3},
          children: [{name: grain, material: oxide, shape: {type: box, size: [0.08, 0.08, 0.08]}}]}
bodies:
  - name: block
    material: steel
    shape: {type: difference, of: [{type: box, size: [10, 10, 4]},
                                   {type: cylinder, diameter: 1.5, height: 6, position: [3, 3, 0],
                                    rotation: {euler_deg: [0, 90, 0]}}]}
    children:
      - {name: insert, material: oxide, shape: {type: sphere, diameter: 2, position: [-2, 2, 0]}}
      - {use: clast, position: [2, -2, 0], rotation: {axis: [1, 1, 0], angle_deg: 30}, scale: 1.5}
    fill:
      - {material: rock, fraction: 0.05, size_mm: [0.1, 0.5], grain: {type: blob, wobble: 0.1},
         orientation: {axis: [0, 1, 0], spread_deg: 10}, clusters: {count: 4, spread_mm: 0.5}}
      - {use: clast, count: 50, scale: [0.6, 1.4]}
      - {pores: {porosity: 0.02, correlation_mm: 0.1, voxel_mm: 0.025, material: void}}
  - name: tomogram
    voxels: {file: segmented.tif, voxel_mm: 0.0062, materials: {1: rock, 2: hrich}}
    position: [0, 0, 0]
```

**Shapes** (`shapes.py`): `box`, `sphere`, `ellipsoid`, `cylinder` and `cone` (axis y), `torus`, `superellipsoid`,
`halfspace`, `prism` (a polygon extruded along z), `blob` (a lumpy ellipsoid), `sawn_piece` (a sawn piece of rock,
a mesh), `mesh` (STL, OBJ, OFF, PLY via trimesh; must be watertight), and `union`, `intersection`, `difference` of
any of them. Each has `position` and `rotation` (`euler_deg: [z, x, y]`, `axis` + `angle_deg`, or `matrix`).
**Voxel bodies**: a 3D array of labels (`.npy`, `.tif` stacks, `.h5:dataset`), one material per label; they lie under
their sibling bodies (a grain over a pore keeps its part). **Fills** (`generators.py`): grains of any shape or copies
of a component (count or volume fraction; uniform, log-normal or measured sizes; aspects; random, fixed or textured
orientations; clusters, shared between populations with `group`), placed without overlap from the largest down;
Voronoi polycrystals (several phases); pores from a thresholded Gaussian random field.

## Accuracy (`tests/test_geometry.py`, `python -m pytest samplecraft/tests`)

* Chords of spheres, boxes and cylinders against closed forms: 1e-12 mm.
* The integral of the chords over a grid of parallel rays equals the exact volume of every shape (box, sphere,
  rotated ellipsoid, cylinder, cone, torus, superellipsoid, lumpy blob, prism), in two directions, to the quadrature
  error of the grid (< 3e-4 at 10 µm); CSG against closed forms (napkin ring, lens, hemisphere): < 1e-4; a
  triangulated sphere against the volume of its triangles: < 2e-5.
* Implicit shapes (lumpy blobs, tori, superellipsoids): sampled at 1/16 of their smallest semi-axis, every sign
  change refined by bisection to the last bit, local minima checked for grazing rays: the batched kernel and the
  single-shape kernel agree with a reference sampled 1000 times finer to 4e-14 mm.
* Voxels: exact traversal (Amanatides & Woo 1987).
* In the ODIN twin, the scene path and the former list-of-volumes path give the same transmission to 1e-13 on the
  samples of the library (3 angles, a stage offset).
* `Scene.check()` tests the tree on points drawn inside each body: an overlap smaller than about 1/n of a body's
  volume can be missed (n = 4000 by default).

## Fitting a sample to a measurement (`fit.py`, `tests/test_fit.py`)

Any number of a recipe is a parameter (its path: `materials.duplex.mix.ferrite`, `bodies.plate.shape.size.2`, list
elements by index or by `name`), with bounds, fixed or free, and ties (`{"materials.duplex.mix.austenite": "1 - f"}`)
— the idea of the EasyScience libraries. `fit.fit(recipe, params, o, d, wavelengths, T, dT)` fits them to a measured
transmission (an image, spectra, or both) by least squares and gives values, errors, correlations and χ²/dof.
Materials only: the path lengths are computed once (a spectrum of 80 wavelengths: 0.4 s); geometry: the scene is
rebuilt at each step, and each pixel is averaged over several rays (`fit.image_rays`), otherwise a small change of a
size moves no ray across an edge. Tests (noisy measurements made from the model, 2026-11-20): ferrite fraction of a
duplex plate from its Bragg edges 0.348 ± 0.002 (true 0.35), χ²/dof 1.00; thickness and hole of a plate from a
40 × 40 image 2.492 ± 0.004 mm and 3.194 ± 0.002 mm (true 2.5 and 3.2), χ²/dof 1.22: with 16 rays per pixel the
model's own sampling adds to the noise and the errors are somewhat too small (use more rays for a paper). Generated
microstructures (counts, Voronoi phase fractions) change by steps with the seed fixed: fit them as a `mix`, or scan.

## Cross-check with McStas Union (`union.py`, `union_check.py`)

`union.export(scene, out_dir)` writes the same sample as McStas Union volumes (how each shape goes to Union: the
docstring of `union.py`) and a test instrument; `python -m samplecraft.union_check <scene.yml> <out_dir>` runs it
(in the `mcstas` environment) and compares the unscattered neutrons with `exp(−Σ Σ_m L_m)`. Two things Union
needs: no faces shared by two volumes (cells of a polycrystal and holders are exported 100 nm inside their faces;
`as_exported` is the scene with exactly those shapes), and, in McStas 3.9.2, a corrected `union-lib.c`:
`r_within_mesh` leaks about 0.5 kB per mesh and per neutron (20 GB per process for 400 grains and 10⁵ neutrons). The
export writes a corrected copy next to the instrument, which McStas reads before its own (fixed upstream since
McStas 3.10.0: then nothing is written). Union stops a process after
100 rays lost on surfaces: the check runs in chunks (`--chunk`). With the fix, a process stays at about 150 MB;
400 meshes cost about 4 ms per neutron and per process.

## What to state in a paper

The scene file (it is the sample: seed, every shape, every material and its source, the assumptions), the version
of samplecraft (`samplecraft.__version__`) and of NCrystal, and the result of `check()`.
