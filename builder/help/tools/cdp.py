"""Drives a headless Chrome (DevTools protocol) on the sample builder, for the pictures of its help."""
import asyncio, base64, json, os, subprocess, sys, time, urllib.request
from tornado.websocket import websocket_connect

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ROOT = os.path.dirname(os.path.abspath(__file__))
URL = "http://127.0.0.1:8899/twin/builder?instrument=odin&proposal=1234&token=helpshots"


class Page:
    async def start(self, w=1440, h=900):
        self.proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333",
                                      "--user-data-dir=" + os.path.join(ROOT, "chrome_profile"), f"--window-size={w},{h}",
                                      "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars",
                                      "--force-device-scale-factor=1", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
                ws = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                await asyncio.sleep(0.3)
        self.ws = await websocket_connect(ws, max_message_size=200 * 2 ** 20)
        self.n = 0
        await self.cmd("Page.enable"); await self.cmd("Runtime.enable")
        await self.cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)

    async def cmd(self, method, **params):
        self.n += 1
        my = self.n
        await self.ws.write_message(json.dumps(dict(id=my, method=method, params=params)))
        while True:
            m = json.loads(await self.ws.read_message())
            if m.get("id") == my:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})

    async def js(self, expr, wait=True):
        r = await self.cmd("Runtime.evaluate", expression=expr, awaitPromise=wait, returnByValue=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(f"JS: {r['exceptionDetails'].get('exception', {}).get('description', r['exceptionDetails'])}")
        return r.get("result", {}).get("value")

    async def until(self, expr, timeout=120):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if await self.js(f"(() => {{ try {{ return !!({expr}); }} catch (e) {{ return false; }} }})()"):
                return True
            await asyncio.sleep(0.4)
        raise TimeoutError(expr)

    async def idle(self, timeout=180):
        """Until the page has nothing being built (the status line empty or not 'Building')."""
        await asyncio.sleep(0.8)
        await self.until("!/Building|Loading|Checking/.test(document.getElementById('status').textContent)", timeout)
        await asyncio.sleep(1.2)

    async def shot(self, name, selector=None, pad=6, clip=None):
        if selector:
            await self.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'start'}})")
            await asyncio.sleep(0.6)
            clip = await self.js(f"""(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();
                return {{x: Math.max(0, r.x - {pad}), y: Math.max(0, r.y - {pad}), width: r.width + 2 * {pad}, height: r.height + 2 * {pad}, scale: 1}}; }})()""")
        kw = dict(format="png")
        if clip:
            kw["clip"] = clip; kw["captureBeyondViewport"] = True
        d = await self.cmd("Page.captureScreenshot", **kw)
        with open(os.path.join(ROOT, "shots", name + ".png"), "wb") as f:
            f.write(base64.b64decode(d["data"]))
        print("shot", name, flush=True)

    async def size(self, w, h):
        await self.cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
        await asyncio.sleep(1.0)

    def stop(self):
        self.proc.terminate()
