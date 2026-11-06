"""Kernels kept ready for the app: pages and notebooks open faster (a few seconds less each time).

The server of the app keeps `pool_size` Python kernels started, with the heavy libraries already imported (numpy,
scipy, scipp, matplotlib, ipywidgets, h5py). When a page (Voila) or a notebook asks for a kernel, it gets one of them:
the kernel is first moved to the folder of the notebook and given the environment of the request (the account of the
student, the address of the page: QUERY_STRING...), as a new kernel would have; then the pool is filled again.

    jupyter server --ServerApp.kernel_manager_class=twin_kernels.PooledKernelManager   (container/ in PYTHONPATH)

Used by the server of the app (app/backend.js, container/start.sh) only with TWIN_KERNEL_POOL=1: OFF by default.
On 2026-11-06 a notebook given a kept kernel froze once in two tries (its cells stopped running, without error), a
fresh kernel never did; to be understood before it is used.
"""
import asyncio
import json
import os

from jupyter_server.services.kernels.kernelmanager import AsyncMappingKernelManager
from traitlets import Integer, Unicode

PRELOAD = ("import numpy, scipy, scipy.optimize, scipy.special, scipp, h5py, matplotlib, matplotlib.pyplot, "
           "ipywidgets, IPython.display")


class PooledKernelManager(AsyncMappingKernelManager):
    pool_size = Integer(2, config=True, help="number of kernels kept ready")
    preload = Unicode(PRELOAD, config=True, help="code run in the kept kernels (imports)")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ready = []            # ids of the kernels ready to be given
        self._filling = False

    async def _run(self, kernel_id, code, timeout=180):
        kc = self.get_kernel(kernel_id).client()
        kc.start_channels()
        try:
            await kc.wait_for_ready(timeout=60)
            reply = await kc.execute_interactive(code, timeout=timeout, store_history=False, output_hook=lambda m: None)
            if reply["content"]["status"] != "ok":
                raise RuntimeError(f"{reply['content'].get('ename')}: {reply['content'].get('evalue')}")
        finally:
            kc.stop_channels()

    async def fill(self):
        """Starts kernels until pool_size are ready (one at a time, in the background)."""
        if self._filling:
            return
        self._filling = True
        try:
            while len(self._ready) < self.pool_size:
                kid = await super().start_kernel(kernel_name=self.default_kernel_name, path="")
                try:
                    await self._run(kid, self.preload)
                except Exception as e:                       # noqa: BLE001
                    self.log.warning("twin_kernels: preload failed (%s); kernel not kept", e)
                    await super().shutdown_kernel(kid, now=True)
                    return
                self._ready.append(kid)
                self.log.info("twin_kernels: kernel %s ready (%d kept)", kid, len(self._ready))
        finally:
            self._filling = False

    async def start_kernel(self, *args, kernel_id=None, path=None, kernel_name=None, env=None, **kwargs):
        name = kernel_name or self.default_kernel_name
        while kernel_id is None and name == self.default_kernel_name and self._ready:
            kid = self._ready.pop(0)
            if kid not in self:
                continue
            cwd = self.cwd_for_path(path, env=env or {}) if path is not None else self.root_dir
            environ = {k: v for k, v in {**os.environ, **(env or {})}.items() if isinstance(v, str)}
            code = (f"import os, json\nos.environ.update(json.loads({json.dumps(json.dumps(environ))}))\n"
                    f"os.chdir({os.path.abspath(cwd)!r})")
            try:
                await self._run(kid, code, timeout=30)
            except Exception as e:                           # noqa: BLE001
                self.log.warning("twin_kernels: kept kernel %s not usable (%s)", kid, e)
                await super().shutdown_kernel(kid, now=True)
                continue
            self.log.info("twin_kernels: kernel %s given for %s", kid, path)
            asyncio.ensure_future(self.fill())
            return kid
        kid = await super().start_kernel(*args, kernel_id=kernel_id, path=path, kernel_name=kernel_name, env=env,
                                         **kwargs)
        asyncio.ensure_future(self.fill())
        return kid

    async def shutdown_kernel(self, kernel_id, *args, **kwargs):
        if kernel_id in self._ready:
            self._ready.remove(kernel_id)
        return await super().shutdown_kernel(kernel_id, *args, **kwargs)

    async def shutdown_all(self, *args, **kwargs):
        self._ready.clear()
        return await super().shutdown_all(*args, **kwargs)

    def kept(self):
        return list(self._ready)
