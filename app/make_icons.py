"""Makes the icons of the app from icon.svg: icon.png (1024 px, the window and the installer), and
../container/app_icon.png and app_icon.ico (the Windows shortcut). Rendered by Edge or Chrome without a window
(transparent background), then scaled with Pillow.

    python make_icons.py
"""
import os
import shutil
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe", "google-chrome", "chromium", "msedge"]


def render(svg, size, out):
    browser = next((b for b in BROWSERS if os.path.isfile(b) or shutil.which(b)), None)
    if not browser:
        raise SystemExit("no Edge or Chrome to render the SVG")
    with tempfile.TemporaryDirectory() as d:
        page = os.path.join(d, "icon.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(f"<!doctype html><html><body style='margin:0;background:transparent'>"
                    f"<img src='file:///{svg.replace(os.sep, '/')}' width='{size}' height='{size}'></body></html>")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--default-background-color=00000000", f"--window-size={size},{size}",
                        f"--screenshot={out}", "file:///" + page.replace(os.sep, "/")],
                       check=True, capture_output=True, timeout=60)


def main():
    svg = os.path.join(HERE, "icon.svg")
    big = os.path.join(HERE, "icon.png")
    render(svg, 1024, big)
    img = Image.open(big).convert("RGBA")
    assert img.getpixel((0, 0))[3] == 0, "the corners should be transparent"
    cont = os.path.join(HERE, "..", "container")
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(cont, "app_icon.png"))
    img.save(os.path.join(cont, "app_icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("written: icon.png, ../container/app_icon.png, ../container/app_icon.ico")


if __name__ == "__main__":
    main()
