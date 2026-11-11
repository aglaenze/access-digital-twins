"""The McStas environment of the twins, set even when the Python of the conda environment is started directly (the
local app, a NICOS launched by it, a scheduled task) rather than from an activated environment.

An activated conda environment of McStas sets MCSTAS (the component library, read by McStasScript to find components
such as Progress_bar) and puts mcrun on the PATH. A Python started without activation has neither: McStasScript then
fails with "No component named Progress_bar in McStas installation" and the shell with "'mcrun' is not recognized".
setup() adds what is missing, from the environment of the running Python (sys.prefix). Imported first by
odin_paths.py and loki_paths.py.
"""
import os
import sys


def setup():
    prefix = sys.prefix
    lib = os.path.join(prefix, "share", "mcstas", "resources")
    if "MCSTAS" not in os.environ and os.path.isdir(lib):
        os.environ["MCSTAS"] = lib
    dirs = ([os.path.join(prefix, d) for d in ("bin", "Scripts", os.path.join("Library", "bin"),
                                                os.path.join("Library", "usr", "bin"), os.path.join("Library", "mingw-w64", "bin"))]
            + [prefix] if os.name == "nt" else [os.path.join(prefix, "bin")])
    path = os.environ.get("PATH", "").split(os.pathsep)
    missing = [d for d in dirs if os.path.isdir(d) and d not in path]
    if missing:
        os.environ["PATH"] = os.pathsep.join(missing + path)
    if os.name == "nt":
        _msvc()


def _msvc():
    """Windows: the C compiler of Visual Studio (cl.exe, its INCLUDE and LIB), which McStas needs to compile an
    instrument. The activation of the conda environment runs vcvars64.bat; without it, it is run here once and its
    environment cached (TWIN_RUN_ROOT/msvc_env.json)."""
    import json
    import shutil
    import subprocess
    if shutil.which("cl") and os.environ.get("INCLUDE"):
        return
    cache = os.path.join(os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin")),
                         "msvc_env.json")
    env = None
    try:
        with open(cache, encoding="utf-8") as f:
            env = json.load(f)
        if not os.path.isfile(os.path.join(env.get("_cl_dir", ""), "cl.exe")):
            env = None
    except (OSError, ValueError):
        pass
    if env is None:
        vswhere = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                               "Microsoft Visual Studio", "Installer", "vswhere.exe")
        if not os.path.isfile(vswhere):
            return
        r = subprocess.run([vswhere, "-latest", "-products", "*", "-requires",
                            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                           capture_output=True, text=True)
        vcvars = os.path.join(r.stdout.strip(), "VC", "Auxiliary", "Build", "vcvars64.bat")
        if not os.path.isfile(vcvars):
            return
        out = subprocess.run(f'"{vcvars}" >nul && set', capture_output=True, text=True, shell=True).stdout
        env = {}
        for line in out.splitlines():
            k, sep, v = line.partition("=")
            if sep and k.upper() in ("PATH", "INCLUDE", "LIB", "LIBPATH", "VCINSTALLDIR", "VCTOOLSINSTALLDIR",
                                      "WINDOWSSDKDIR", "WINDOWSSDKVERSION", "UCRTVERSION", "UNIVERSALCRTSDKDIR"):
                env[k.upper()] = v
        cl = shutil.which("cl", path=env.get("PATH", ""))
        if not cl:
            return
        env["_cl_dir"] = os.path.dirname(cl)
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(env, f)
        except OSError:
            pass
    for k, v in env.items():
        if k == "PATH":
            mine = os.environ.get("PATH", "").split(os.pathsep)
            os.environ["PATH"] = os.pathsep.join(mine + [d for d in v.split(os.pathsep) if d and d not in mine])
        elif not k.startswith("_"):
            os.environ[k] = v
    os.environ.setdefault("MCSTAS_CC", "cl.exe")


setup()
