"""Starts Voila (same arguments as "python -m voila"), with one fix for the pre-heated kernels on Windows.

Voila (0.5) names the pool of pre-heated kernels of a page after its path on disk, made with the separator of the
system ("odin\\exercises\\...\\page.ipynb" on Windows), but looks the pool up with the path of the address
("odin/exercises/.../page.ipynb"): on Windows a pre-heated kernel is never used, and every student waits for a new
kernel. Here every page name is written with "/" before the pools are used. On Linux (the container) nothing changes.

    python container/voila_launch.py <arguments of voila>          (web_class.py does it)
"""
import sys


def _norm(name):
    return name.replace("\\", "/") if isinstance(name, str) else name


class _Paths(dict):
    """A dict whose keys (page paths) are written with "/"."""

    def __getitem__(self, k):
        return super().__getitem__(_norm(k))

    def __setitem__(self, k, v):
        super().__setitem__(_norm(k), v)

    def __contains__(self, k):
        return super().__contains__(_norm(k))

    def get(self, k, default=None):
        return super().get(_norm(k), default)

    def setdefault(self, k, default=None):
        return super().setdefault(_norm(k), default)


def _patch():
    import voila.app
    import voila.voila_kernel_manager as vkm
    factory = vkm.voila_kernel_manager_factory

    def patched_factory(base_class, preheat_kernel, default_pool_size, **kwargs):
        cls = factory(base_class, preheat_kernel, default_pool_size, **kwargs)
        if not preheat_kernel or not hasattr(cls, "fill_if_needed"):
            return cls

        class SlashPaths(cls):
            def __setattr__(self, name, value):
                if name in ("_pools", "notebook_data") and isinstance(value, dict) and not isinstance(value, _Paths):
                    value = _Paths({_norm(k): v for k, v in value.items()})
                super().__setattr__(name, value)

            def fill_if_needed(self, delay=None, notebook_name=None, **kw):
                return super().fill_if_needed(delay=delay, notebook_name=_norm(notebook_name), **kw)

            async def get_rendered_notebook(self, notebook_name, *a, **kw):
                return await super().get_rendered_notebook(_norm(notebook_name), *a, **kw)

            def get_pool_size(self, notebook_name):
                return super().get_pool_size(_norm(notebook_name))

        SlashPaths.__name__ = cls.__name__          # the configuration section stays "VoilaKernelManager"
        return SlashPaths

    voila.app.voila_kernel_manager_factory = patched_factory


if __name__ == "__main__":
    if sys.platform == "win32":
        _patch()
    from voila.app import main
    sys.exit(main())
