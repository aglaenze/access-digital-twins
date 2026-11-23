"""The pictures of the help of the sample builder (builder/help/*.png, then turned into .webp): a headless Chrome
drives the real page (cdp.py). Start a local server first, on port 8899 with the token "helpshots":
    python -m jupyter_server --port=8899 --IdentityProvider.token=helpshots \
        "--ServerApp.jpserver_extensions={'twin_app': True}"     (PYTHONPATH=container, from twin/)
then:  python builder/help/tools/shots.py   (pictures in builder/help/tools/shots/; delete chrome_profile/ before,
so that the page starts as at a first visit)."""
import asyncio, os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Page, URL

CLICK = "(sel) => document.querySelector(sel).click()"

async def click(p, sel):
    await p.js(f"document.querySelector({sel!r}).click()")

async def set_number(p, label, value):
    """The number box of the slider row whose label starts with `label`, in the part panel."""
    await p.js(f"""(() => {{ const row = [...document.querySelectorAll('#part .slider')].find(r => r.querySelector('.nm').textContent.trim().startsWith({label!r}));
        const n = row.querySelector('input[type=number]'); n.value = {value}; n.dispatchEvent(new Event('change')); return true; }})()""")

async def main():
    p = Page(); await p.start(1440, 900)
    try:
        # the tour (started by itself at a first visit) marked as seen, so that it is not in the pictures
        await p.cmd("Page.navigate", url=URL)
        await p.until("document.getElementById('help-btn')", 60)
        await p.js("localStorage.setItem('twin-builder-toured', '1')")
        # 1. the page with the iron plate
        await p.cmd("Page.navigate", url=URL + "&start=iron_plate")
        await p.until("document.querySelectorAll('#gallery .card').length > 5")
        await p.idle()
        await p.shot("overview")
        await p.js("document.getElementById('panel').scrollTop = 0")
        # 2. the gallery
        await p.js("document.getElementById('gallery-box').open = true; document.getElementById('gallery').style.maxHeight = 'none'")
        await p.size(1440, 1700)
        await p.shot("gallery", "#gallery-box")
        await p.size(1440, 900)
        await p.js("document.getElementById('gallery-box').open = false")
        # 3. a copper insert in the iron plate: + Inside, material copper, diameter 4 mm
        await click(p, "#add-inside"); await asyncio.sleep(0.8)
        await p.js("[...document.querySelectorAll('#part .matcard button')].find(b => b.textContent === 'Change').click()")
        await asyncio.sleep(0.5)
        await p.js("const s = document.getElementById('mat-search'); s.value = 'nickel'; s.dispatchEvent(new Event('input'))")
        await asyncio.sleep(0.6)
        await p.shot("picker", "#picker .sheet")
        await p.js("[...document.querySelectorAll('#mat-list .mcard')].find(c => /nickel/i.test(c.textContent)).click()")
        await asyncio.sleep(0.6)
        await set_number(p, "diameter", 4)
        await p.idle()
        await p.shot("tree", ".box:has(#tree)")
        await p.shot("part", "#part-box")
        await p.shot("insert_3d", "#viewer")
        # 4. the beam's eye view
        await p.js("document.querySelector('.vtabs [data-view=beam]').click()")
        await p.until("document.getElementById('radio').src.startsWith('data:')", 120)
        await asyncio.sleep(1.5)
        await p.shot("beam", "#viewer")
        await p.js("document.querySelector('.vtabs [data-view=\"3d\"]').click()")
        # 5. step 2 and step 3
        await p.js("document.querySelector('#steps [data-step=\"2\"]').click()"); await asyncio.sleep(1.5)
        await p.shot("holder", "#step2")
        await p.js("document.querySelector('#steps [data-step=\"3\"]').click()")
        await p.until("!document.querySelector('#checks .wait')", 120); await asyncio.sleep(1.5)
        await p.shot("check", "#step3")
        # 6. grains: the duplex steel, Advanced open
        await p.cmd("Page.navigate", url=URL + "&start=")
        await p.until("document.querySelectorAll('#gallery .card').length > 5")
        await p.js("[...document.querySelectorAll('#gallery .card')].find(c => /Duplex/.test(c.textContent)).click()")
        await p.idle(240)
        if not await p.js("document.getElementById('grains').checked"):
            await p.js("document.getElementById('grains').click()")
            await p.idle(240)
        await p.js("document.querySelector('#part details.sub-box:last-of-type').open = true"); await asyncio.sleep(2.5)
        await p.shot("grains_adv", "#part details.sub-box:last-of-type")
        await p.shot("grains_3d", "#viewer")
        print("status:", await p.js("document.getElementById('status').textContent"))
    finally:
        p.stop()
asyncio.run(main())
