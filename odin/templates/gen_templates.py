"""Writes the examples of the sample builder (odin/templates/*.yml): samplecraft recipes to start from and change.

    python gen_templates.py

A template: {name, title, description, instrument, recipe} (recipe: a samplecraft scene description). The students'
own models are written by the sample builder in <TWIN_RUN_ROOT>/templates/odin/, in the same format. The numbers
that are not textbook values say where they come from (source of each material, provenance of the recipe).
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))          # twin/
import sample_library as sl  # noqa: E402

# the matrix of NWA 7034, its Σ(1.8 Å) set to 0.45 cm⁻¹ as measured at ICON (odin/samples/gen_nwa7034.py)
MATRIX = {"calibrate": {"base": {"minerals": dict(plag=38, opx=25.4, cpx=18.2, mag=9.7, afs=4.9, ap=3.7)},
                        "add": "water", "sigma_cm": 0.45, "wavelength_A": 1.8},
          "source": "Naver et al., arXiv:2601.08390, Table S2 (matrix at ICON); mineralogy of Agee et al. 2013"}
AL = {"ncrystal": "Al_sg225.ncmat", "source": "NCrystal library"}
HOLDER_PIN = dict(name="aluminium pin", material="aluminium", holder=True,
                  shape={"type": "cylinder", "diameter": 3.0, "height": 6.0, "position": [0.0, -9.0, 0.0]})

TEMPLATES = {
    "martian_breccia": dict(
        title="Martian breccia (like NWA 7034)",
        description="A sawn piece (8 × 12 × 2 mm) of a Martian breccia: the fine matrix of NWA 7034 (its Σ measured "
                    "at ICON), clasts of plagioclase and pyroxene (5 % each), Fe-Ti oxide grains, pores, and "
                    "hydrated clasts (a goethite body with a magnetite grain, a component) gathered in 6 clusters.",
        recipe=dict(
            samplecraft=1, seed=7,
            provenance={"sources": ["Naver et al., arXiv:2601.08390 (2026)"],
                        "assumptions": ["positions random (seed 7)", "clast shape: one component, scaled 0.6 to 1.4"]},
            materials={"matrix": MATRIX, "plagioclase": {"minerals": {"plag": 85, "afs": 15}},
                       "pyroxene": {"minerals": {"opx": 58, "cpx": 42}}, "goethite": {"minerals": {"gt": 100}},
                       "Fe-Ti oxide": {"minerals": {"mag": 65, "ilm": 35}}, "void": {"ncrystal": "void.ncmat"},
                       "aluminium": AL},
            components={"hydrated clast": dict(
                material="goethite", shape={"type": "blob", "size": [0.25, 0.32, 0.27], "wobble": 0.12, "seed": 3},
                children=[dict(name="magnetite grain", material="Fe-Ti oxide",
                               shape={"type": "box", "size": [0.07, 0.07, 0.07], "position": [-0.05, 0.0, 0.0],
                                      "rotation": {"euler_deg": [20, 35, 10]}})])},
            bodies=[dict(name="the piece", material="matrix", shape={"type": "sawn_piece", "size": [8, 12, 2], "seed": 11},
                         fill=[{"use": "hydrated clast", "count": 120, "scale": [0.6, 1.4],
                                "clusters": {"count": 6, "spread_mm": 0.35}},
                               {"material": "plagioclase", "fraction": 0.05, "size_mm": [0.1, 0.5],
                                "grain": {"type": "blob", "wobble": 0.12}},
                               {"material": "pyroxene", "fraction": 0.05, "size_mm": [0.1, 0.5],
                                "grain": {"type": "blob", "wobble": 0.12}},
                               {"material": "Fe-Ti oxide", "count": 800,
                                "size": {"lognormal": {"median_mm": 0.04, "sigma": 0.5}, "min_mm": 0.016, "max_mm": 0.08},
                                "aspect": [[0.6, 1], [0.6, 1]], "grain": {"type": "blob", "wobble": 0}},
                               {"material": "void", "count": 40, "size_mm": [0.06, 0.12], "aspect": [[0.7, 1], [0.7, 1]],
                                "grain": {"type": "blob", "wobble": 0.15}, "name": "pore"}]),
                    HOLDER_PIN])),
    "serpentinite_pebble": dict(
        title="Serpentinite pebble (a rock that holds water)",
        description="A lumpy pebble (10 × 8 × 6 mm) of basalt partly turned into serpentine by water: lumps of "
                    "serpentine (13 % of water by mass, as OH) in 3 clusters, olivine and magnetite grains.",
        recipe=dict(
            samplecraft=1, seed=3, provenance={"sources": [], "assumptions": ["textbook mineral compositions"]},
            materials={"basalt": {"minerals": {"plag": 50, "cpx": 35, "ol": 8, "mag": 7}},
                       "serpentine": {"minerals": {"srp": 100}}, "olivine": {"minerals": {"ol": 100}},
                       "magnetite": {"minerals": {"mag": 100}}, "aluminium": AL},
            components={},
            bodies=[dict(name="the pebble", material="basalt",
                         shape={"type": "blob", "size": [10, 8, 6], "wobble": 0.12, "seed": 4,
                                "rotation": {"euler_deg": [20, 10, 0]}},
                         fill=[{"material": "serpentine", "fraction": 0.12, "size_mm": [0.4, 1.5],
                                "grain": {"type": "blob", "wobble": 0.2}, "clusters": {"count": 3, "spread_mm": 1.2}},
                               {"material": "olivine", "fraction": 0.08, "size_mm": [0.2, 0.8],
                                "grain": {"type": "blob", "wobble": 0.1}},
                               {"material": "magnetite", "count": 300, "size_mm": [0.03, 0.15],
                                "aspect": [[0.8, 1], [0.8, 1]], "grain": {"type": "blob", "wobble": 0}}]),
                    dict(name="holder", material="aluminium", holder=True,
                         shape={"type": "box", "size": [12, 2, 8], "position": [0, -5.2, 0]})])),
    "machined_steel_part": dict(
        title="Machined steel part with hidden flaws",
        description="A ferritic steel block with a drilled hole and a chamfered corner (constructive solid geometry), "
                    "a copper insert holding a lead ball, a tilted tungsten inclusion, an elongated pore.",
        recipe=dict(
            samplecraft=1, seed=1, provenance={"sources": [], "assumptions": []},
            materials={"steel": {"ncrystal": "Fe_sg229_Iron-alpha.ncmat"}, "copper": {"ncrystal": "Cu_sg225.ncmat"},
                       "lead": {"ncrystal": "Pb_sg225.ncmat"}, "tungsten": {"ncrystal": "W_sg229.ncmat"},
                       "void": {"ncrystal": "void.ncmat"}, "aluminium": AL},
            components={},
            bodies=[dict(name="steel block", material="steel",
                         shape={"type": "difference", "of": [
                             {"type": "box", "size": [10, 10, 4]},
                             {"type": "cylinder", "diameter": 1.5, "height": 6, "position": [3, 3, 0],
                              "rotation": {"euler_deg": [0, 90, 0]}},
                             {"type": "halfspace", "normal": [-1, -1, 0], "offset": -6.0}]},
                         children=[dict(name="copper insert", material="copper",
                                        shape={"type": "sphere", "diameter": 2.5, "position": [-2.5, 2, 0]},
                                        children=[dict(name="lead ball", material="lead",
                                                       shape={"type": "sphere", "diameter": 1.0, "position": [-2.5, 2, 0]})]),
                                   dict(name="tungsten inclusion", material="tungsten",
                                        shape={"type": "ellipsoid", "size": [3, 1, 1], "position": [2.5, -2, 0.5],
                                               "rotation": {"euler_deg": [35, 0, 20]}}),
                                   dict(name="pore", material="void",
                                        shape={"type": "ellipsoid", "size": [2.5, 0.4, 0.4], "position": [-2, -3, -0.5],
                                               "rotation": {"euler_deg": [-20, 0, 0]}})]),
                    dict(name="holder", material="aluminium", holder=True,
                         shape={"type": "box", "size": [12, 3, 6], "position": [0, -6.5, 0]})])),
    "duplex_steel": dict(
        title="Duplex stainless steel (a polycrystal)",
        description="A plate of duplex steel: 400 grains of ferrite (bcc) and austenite (fcc), half each (a Voronoi "
                    "polycrystal). Bragg-edge imaging tells the two phases apart.",
        recipe=dict(
            samplecraft=1, seed=5, provenance={"sources": [], "assumptions": ["equiaxed grains (Voronoi)"]},
            materials={"ferrite": {"ncrystal": "Fe_sg229_Iron-alpha.ncmat"},
                       "austenite": {"ncrystal": "Fe_sg225_Iron-gamma.ncmat"}, "aluminium": AL},
            components={},
            bodies=[dict(name="plate", material="ferrite", shape={"type": "box", "size": [8, 8, 2]},
                         fill=[{"voronoi": {"count": 400, "phases": {"ferrite": 0.5, "austenite": 0.5}}}]),
                    dict(name="holder", material="aluminium", holder=True,
                         shape={"type": "box", "size": [10, 2, 4], "position": [0, -5, 0]})])),
    "porous_sandstone": dict(
        title="Porous sandstone with clay",
        description="A cylinder of sandstone (6 mm across, 8 mm high): quartz with 15 % of pores (a Gaussian random "
                    "field, 0.1 mm correlation) and aggregates of kaolinite clay (3 %), which hold hydrogen (as OH).",
        recipe=dict(
            samplecraft=1, seed=9, provenance={"sources": [], "assumptions": [
                "porosity and clay content typical of sandstones",
                "kaolinite aggregates (booklets of crystals of a few micrometers, far below the resolution) described "
                "as one porous material: 40 % of microporosity (density factor 0.6)"]},
            materials={"quartz": {"minerals": {"qz": 100}}, "clay": {"minerals": {"kln": 100}, "density_factor": 0.6},
                       "void": {"ncrystal": "void.ncmat"}, "aluminium": AL},
            components={},
            bodies=[dict(name="core", material="quartz", shape={"type": "cylinder", "diameter": 6, "height": 8},
                         fill=[{"material": "clay", "fraction": 0.03, "size_mm": [0.15, 0.4], "name": "clay aggregate",
                                "aspect": [[0.6, 1], [0.5, 0.8]], "grain": {"type": "blob", "wobble": 0.15}},
                               {"pores": {"porosity": 0.15, "correlation_mm": 0.1, "voxel_mm": 0.04}}]),
                    dict(name="holder", material="aluminium", holder=True,
                         shape={"type": "cylinder", "diameter": 6, "height": 2, "position": [0, -5, 0]})])),
}

if __name__ == "__main__":
    for f in os.listdir(HERE):
        if f.endswith(".yml"):
            os.remove(os.path.join(HERE, f))
    for name, t in TEMPLATES.items():
        with open(os.path.join(HERE, name + ".yml"), "w", encoding="utf-8") as f:
            f.write("# Generated by gen_templates.py: an example of the sample builder (a samplecraft recipe).\n")
            yaml.safe_dump(dict(name=name, instrument="odin", **t), f, sort_keys=False, allow_unicode=True, width=120,
                           default_flow_style=None)
        print("written", name)
