"""The look of the figures drawn with matplotlib: the font of the app (IBM Plex Sans, shipped in fonts/ under the SIL
Open Font License, fonts/OFL.txt) and its palette (ink, green of the beam, the colors of the catalogue).

    import plot_style
    plot_style.use()               # registers the font, sets the defaults of matplotlib
    plot_style.INK, plot_style.GREEN, ...
"""
import glob
import os

INK, GREEN, ORANGE, GREY, RED, BLUE = "#1B1F24", "#1E7B4E", "#C7711A", "#8A938A", "#B4562B", "#2F5FB3"
MUTED, LINE, PAPER = "#566057", "#D5D9D1", "#F4F5F1"
FONT = ["IBM Plex Sans", "DejaVu Sans"]       # DejaVu: the glyphs Plex has not (a few math symbols)
_done = []


def use():
    """Registers the fonts of fonts/ with matplotlib (once) and sets its defaults to the look of the app."""
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    if not _done:
        for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "*.ttf")):
            font_manager.fontManager.addfont(f)
        _done.append(True)
    plt.rcParams.update({"font.family": FONT, "font.size": 11, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                         "xtick.color": INK, "ytick.color": INK, "text.color": INK})
