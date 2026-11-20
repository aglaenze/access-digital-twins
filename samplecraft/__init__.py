"""samplecraft: models of samples for neutron (and X-ray) imaging and scattering, as exact geometry.

    import samplecraft as sc
    scene = sc.Scene.load("my_sample.yml")          # components expanded, microstructures generated (seeded)
    scene.check()                                   # every body inside its parent, no two siblings overlapping
    L = scene.material_lengths(o, d)                # exact path length in each material along rays o + t d (mm)
    T = scene.transmission(o, d, wavelength_A=3.0)  # Beer–Lambert with NCrystal cross-sections

Shapes (shapes.py): box, sphere, ellipsoid, cylinder, cone, torus, superellipsoid, half-space, prism, lumpy blob,
triangle mesh (STL/OBJ/OFF/PLY), and their unions, intersections and differences, each with a position and any 3D
rotation. Voxel bodies: segmented tomograms (.npy, .tif, .h5). Generators (generators.py): grains of any shape or
composite components (sizes, aspects, orientations or textures, clusters), Voronoi polycrystals, porosity from
Gaussian random fields. Materials (materials.py): NCrystal crystals, compositions, minerals, mixtures, porosity,
calibration on a measured attenuation. Fits (fit.py): any number of a recipe fitted to a measured image or spectrum.
Cross-check (union.py): export to McStas Union. Validation: samplecraft/tests (python -m pytest samplecraft/tests).
"""
from .intervals import IntervalSet
from .materials import resolve as resolve_materials, sigma
from .scene import Body, Scene, VoxelBody
from .shapes import make as make_shape, rotation

__version__ = "1.0.0"
