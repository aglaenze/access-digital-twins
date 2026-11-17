"""Writes the examples of the sample builder (odin/templates/*.yml): recipes the students start from and change.

    python gen_templates.py

A template: {name, title, description, instrument, recipe} (recipe: rock_builder.build_sample). The students' own
models are written by the sample builder in <TWIN_RUN_ROOT>/templates/odin/, in the same format.
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))          # twin/
import rock_builder as rb  # noqa: E402

M = rb.rock_mineral
# the matrix of NWA 7034, its Σ(1.8 Å) set to 0.45 cm⁻¹ as measured at ICON (odin/samples/gen_nwa7034.py)
with open(os.path.join(HERE, "..", "samples", "meteorite_nwa7034.yml"), encoding="utf-8") as f:
    MATRIX = yaml.load(f, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))["materials"]["matrix"]

TEMPLATES = {
    "martian_breccia": dict(
        title="Martian breccia (like NWA 7034)",
        description="A sawn piece (8 × 12 × 2 mm) of a Martian breccia: the fine matrix of NWA 7034 (its Σ measured "
                    "at ICON), clasts of plagioclase and pyroxene (5 % each), small Fe-Ti oxide grains, a few pores, "
                    "and goethite, an iron oxide that holds hydrogen, in 6 clusters. A simpler cousin of the "
                    "meteorite of the exercise: change the amounts, sizes and clusters.",
        recipe=dict(
            seed=7,
            piece=dict(shape="sawn piece (irregular edges)", material="NWA 7034 matrix", size_mm=[8.0, 12.0, 2.0]),
            objects=[],
            populations=[
                dict(material="plagioclase (feldspar)", fraction_pct=5.0, size_mm=[0.1, 0.5], grain_shape="irregular",
                     lumps=0.12, clusters=0, inside="piece"),
                dict(material="pyroxene", fraction_pct=5.0, size_mm=[0.1, 0.5], grain_shape="irregular", lumps=0.12,
                     clusters=0, inside="piece"),
                dict(material="goethite FeO(OH) (holds H)", fraction_pct=0.4, size_mm=[0.1, 0.3],
                     grain_shape="irregular", lumps=0.15, clusters=6, spread_mm=0.35, inside="piece"),
                dict(material="Fe-Ti oxide (magnetite + ilmenite)", count=800, size_mm=[0.02, 0.08],
                     grain_shape="round", lumps=0.0, clusters=0, inside="piece"),
                dict(material="void", count=40, size_mm=[0.06, 0.12], grain_shape="round", lumps=0.15, clusters=0,
                     inside="piece"),
            ],
            holders=[dict(shape="cylinder", material="Al_sg225.ncmat", center_mm=[0, -9.0, 0], size_mm=[3.0, 6.0])],
            materials={"NWA 7034 matrix": MATRIX, "plagioclase (feldspar)": M("plagioclase (feldspar)"),
                       "pyroxene": M("pyroxene"), "goethite FeO(OH) (holds H)": M("goethite FeO(OH) (holds H)"),
                       "Fe-Ti oxide (magnetite + ilmenite)": M("Fe-Ti oxide (magnetite + ilmenite)"),
                       "void": "void.ncmat"})),
    "serpentinite_pebble": dict(
        title="Serpentinite pebble (a rock that holds water)",
        description="A lumpy pebble (10 × 8 × 6 mm) of basalt partly turned into serpentine by water: lumps of "
                    "serpentine (it holds 13 % of water by mass, as OH) and grains of olivine and magnetite.",
        recipe=dict(
            seed=3,
            piece=dict(shape="lumpy (pebble, grain)", material="basalt (fine-grained)", size_mm=[10.0, 8.0, 6.0],
                       angles_deg=[20, 10, 0], lumps=0.12),
            objects=[],
            populations=[
                dict(material="serpentine (holds H)", fraction_pct=12.0, size_mm=[0.4, 1.5], grain_shape="irregular",
                     lumps=0.2, clusters=3, spread_mm=1.2, inside="piece"),
                dict(material="olivine", fraction_pct=8.0, size_mm=[0.2, 0.8], grain_shape="irregular", lumps=0.1,
                     clusters=0, inside="piece"),
                dict(material="Fe-Ti oxide (magnetite + ilmenite)", count=300, size_mm=[0.03, 0.15],
                     grain_shape="round", lumps=0.0, clusters=0, inside="piece"),
            ],
            holders=[dict(shape="block", material="Al_sg225.ncmat", center_mm=[0, -6.5, 0], size_mm=[12.0, 2.0, 8.0])],
            materials={k: M(k) for k in ("basalt (fine-grained)", "serpentine (holds H)", "olivine",
                                         "Fe-Ti oxide (magnetite + ilmenite)")})),
    "steel_with_inclusions": dict(
        title="Steel block with hidden inclusions",
        description="A block of ferritic steel (10 × 10 × 4 mm) with objects placed by hand: a copper sphere, a "
                    "tilted tungsten ellipsoid, an elongated pore, and inside the copper sphere a small lead ball.",
        recipe=dict(
            seed=1,
            piece=dict(shape="block", material="Fe_sg229_Iron-alpha.ncmat", size_mm=[10.0, 10.0, 4.0]),
            objects=[
                dict(name="copper ball", shape="sphere", material="Cu_sg225.ncmat", center_mm=[-2.5, 2.0, 0.0],
                     size_mm=[2.5], inside="piece"),
                dict(name="lead core", shape="sphere", material="Pb_sg225.ncmat", center_mm=[-2.5, 2.0, 0.0],
                     size_mm=[1.0], inside="copper ball"),
                dict(name="tungsten grain", shape="ellipsoid", material="W_sg229.ncmat", center_mm=[2.5, -2.0, 0.5],
                     size_mm=[3.0, 1.0, 1.0], angles_deg=[35, 0, 20], inside="piece"),
                dict(name="pore", shape="ellipsoid", material="void.ncmat", center_mm=[2.0, 3.0, -0.5],
                     size_mm=[2.5, 0.4, 0.4], angles_deg=[-20, 0, 0], inside="piece"),
            ],
            populations=[],
            holders=[dict(shape="block", material="Al_sg225.ncmat", center_mm=[0, -6.5, 0], size_mm=[12.0, 3.0, 6.0])],
            materials={})),
}

for name, t in TEMPLATES.items():
    with open(os.path.join(HERE, name + ".yml"), "w", encoding="utf-8") as f:
        f.write("# Generated by gen_templates.py: an example of the sample builder.\n")
        yaml.safe_dump(dict(name=name, instrument="odin", **t), f, sort_keys=False, allow_unicode=True, width=120)
    print("written", name)
