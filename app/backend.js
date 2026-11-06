// The server behind the app: Jupyter (pages, notebooks) with the API of the app (container/twin_app.py).
//   local:     the conda environment "mcstas" of this computer and the twin folder next to this app (teachers,
//              developers: the code as it is). Chosen when that Python is found and the app runs from the repository.
//   container: the image of the twins in Podman or Docker (students): pulled the first time, the data in the volume
//              "twin-data".
// Settings (environment or <userData>/settings.json): TWIN_BACKEND (local|container), TWIN_PYTHON, TWIN_IMAGE,
// TWIN_ENGINE (podman|docker).
const { spawn, execFile } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const net = require("net");
const os = require("os");
const path = require("path");

const IMAGE = "ghcr.io/aglaenze/access-digital-twins:latest";
const CONTAINER = "ess-twins-app";

function freePort(start) {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.once("error", () => resolve(freePort(start + 1)));
    s.listen(start, "127.0.0.1", () => s.close(() => resolve(start)));
  });
}

function run(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    execFile(cmd, args, { windowsHide: true, maxBuffer: 1 << 24, ...opts }, (err, stdout, stderr) =>
      resolve({ code: err ? (err.code ?? 1) : 0, stdout: String(stdout || ""), stderr: String(stderr || "") }));
  });
}

function which(names) {
  const dirs = (process.env.PATH || "").split(path.delimiter);
  const exts = process.platform === "win32" ? [".exe", ".cmd", ""] : [""];
  const extra = process.platform === "win32"
    ? ["C:\\Program Files\\RedHat\\Podman", "C:\\Program Files\\Docker\\Docker\\resources\\bin"]
    : ["/opt/podman/bin", "/usr/local/bin", "/opt/homebrew/bin", "/Applications/Docker.app/Contents/Resources/bin"];
  for (const n of names) {
    for (const d of dirs.concat(extra)) {
      for (const e of exts) {
        const p = path.join(d, n + e);
        if (d && fs.existsSync(p)) return p;
      }
    }
  }
  return null;
}

function localPython() {
  if (process.env.TWIN_PYTHON && fs.existsSync(process.env.TWIN_PYTHON)) return process.env.TWIN_PYTHON;
  const h = os.homedir();
  const la = process.env.LOCALAPPDATA || path.join(h, "AppData", "Local");
  const c = process.platform === "win32"
    ? [path.join(la, "miniforge3", "envs", "mcstas", "python.exe"), path.join(h, "miniforge3", "envs", "mcstas", "python.exe"),
       path.join(h, "miniconda3", "envs", "mcstas", "python.exe"), path.join(h, "anaconda3", "envs", "mcstas", "python.exe")]
    : ["miniforge3", "miniconda3", "anaconda3", "mambaforge"].map((d) => path.join(h, d, "envs", "mcstas", "bin", "python"));
  return c.find((p) => fs.existsSync(p)) || null;
}

class Backend {
  // onStatus(text, fraction 0-1) is called while it starts
  constructor({ dataDir, twinDir, settings = {}, onStatus = () => {} }) {
    this.dataDir = dataDir;
    this.twinDir = twinDir;
    this.settings = settings;
    this.onStatus = onStatus;
    this.token = crypto.randomBytes(18).toString("hex");
    this.proc = null;
    this.mode = null;
    this.base = null;
  }

  chooseMode() {
    const want = process.env.TWIN_BACKEND || this.settings.backend;
    if (want) return want;
    const repo = fs.existsSync(path.join(this.twinDir, "container", "twin_app.py"));
    return repo && localPython() ? "local" : "container";
  }

  async start() {
    this.mode = this.chooseMode();
    this.port = await freePort(8890);
    this.base = `http://127.0.0.1:${this.port}`;
    if (this.mode === "local") await this.startLocal();
    else await this.startContainer();
    await this.waitReady();
    return this.base;
  }

  async startLocal() {
    const py = localPython();
    if (!py) throw new Error("No conda environment 'mcstas' found (set TWIN_PYTHON), and no container.");
    this.onStatus("Starting the instruments…", 0.2);
    const c = path.join(this.twinDir, "container");
    const env = { ...process.env, JUPYTER_CONFIG_PATH: path.join(c, "app_config"), JUPYTER_PATH: path.join(c, "app_data"),
                  TWIN_APP_LOCAL: "1", PYTHONPATH: c + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : ""),
                  PYTHONIOENCODING: "utf-8" };
    fs.mkdirSync(this.dataDir, { recursive: true });
    const log = fs.openSync(path.join(this.dataDir, "server.log"), "w");
    // jupyter_server directly (not "jupyter server", which starts it as a second process that would outlive us)
    this.proc = spawn(py, ["-m", "jupyter_server", "--no-browser", "--ServerApp.ip=127.0.0.1", `--port=${this.port}`,
                           `--IdentityProvider.token=${this.token}`, `--ServerApp.root_dir=${this.twinDir}`,
                           "--ServerApp.jpserver_extensions={'twin_app': True}",
                           "--ServerApp.kernel_manager_class=twin_kernels.PooledKernelManager"],
                      { cwd: this.twinDir, env, windowsHide: true, stdio: ["ignore", log, log] });
  }

  async startContainer() {
    const want = process.env.TWIN_ENGINE || this.settings.engine;          // podman or docker; by default the first found
    const eng = which(want ? [want] : ["podman", "docker"]);
    if (!eng) {
      const e = new Error("Podman is needed to run the instruments. Install Podman Desktop (free), then open this app again.");
      e.url = "https://podman-desktop.io";
      throw e;
    }
    this.engine = eng;
    this.onStatus("Starting the container engine…", 0.1);
    if ((await run(eng, ["info"])).code !== 0) {
      if (/podman/i.test(path.basename(eng))) await run(eng, ["machine", "start"]);
      for (let i = 0; i < 90 && (await run(eng, ["info"])).code !== 0; i++) await new Promise((r) => setTimeout(r, 2000));
    }
    const image = process.env.TWIN_IMAGE || this.settings.image || IMAGE;
    if ((await run(eng, ["image", "inspect", image])).code !== 0) {
      this.onStatus("First start: downloading the instruments (several GB, once)…", 0.15);
      const r = await run(eng, ["pull", image], { timeout: 3 * 3600 * 1000 });
      if (r.code !== 0) throw new Error("The download of the instruments failed: " + r.stderr.slice(-300));
    } else {
      execFile(eng, ["pull", "-q", image], { windowsHide: true }, () => {});   // updates for the next time
    }
    this.onStatus("Starting the instruments…", 0.4);
    await run(eng, ["rm", "-f", CONTAINER]);
    const r = await run(eng, ["run", "-d", "--rm", "--name", CONTAINER, "-p", `127.0.0.1:${this.port}:8888`,
                              "-v", "twin-data:/data", ...(process.env.GITHUB_TOKEN ? ["-e", "GITHUB_TOKEN"] : []), image, "jupyter", `--IdentityProvider.token=${this.token}`]);
    if (r.code !== 0) throw new Error("The container did not start: " + r.stderr.slice(-300));
  }

  request(method, p, body, { raw = false, timeout = 60000 } = {}) {
    return new Promise((resolve, reject) => {
      const data = body === undefined ? null : Buffer.from(JSON.stringify(body));
      const req = http.request(this.base + p, { method, timeout, headers: {
        Authorization: "token " + this.token, ...(data ? { "Content-Type": "application/json", "Content-Length": data.length } : {}) } },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const buf = Buffer.concat(chunks);
          if (res.statusCode >= 400) return reject(new Error(`${method} ${p}: ${res.statusCode} ${buf.toString().slice(0, 300)}`));
          if (raw) return resolve({ buf, headers: res.headers });
          try { resolve(buf.length ? JSON.parse(buf) : {}); } catch (e) { reject(e); }
        });
      });
      req.on("timeout", () => req.destroy(new Error("timeout")));
      req.on("error", reject);
      if (data) req.write(data);
      req.end();
    });
  }

  async waitReady() {
    const t0 = Date.now();
    for (;;) {
      try {
        await this.request("GET", "/api/status", undefined, { timeout: 3000 });
        this.onStatus("Instruments ready", 1);
        return;
      } catch {
        if (this.proc && this.proc.exitCode !== null) {
          throw new Error("The server stopped: see " + path.join(this.dataDir, "server.log"));
        }
        // the first start of the container downloads the recorded beams (MCPL files): up to ~15 min
        const limit = this.mode === "container" ? 20 * 60000 : 4 * 60000;
        if (Date.now() - t0 > limit) throw new Error(`The server did not answer within ${limit / 60000} minutes.`);
        const f = Math.min(0.95, 0.4 + (Date.now() - t0) / 60000 * 0.5);
        this.onStatus("Starting the instruments…", f);
        await new Promise((r) => setTimeout(r, 500));
      }
    }
  }

  url(p) {
    return this.base + p + (p.includes("?") ? "&" : "?") + "token=" + this.token;
  }

  async stop() {
    try { await this.request("POST", "/api/shutdown", undefined, { timeout: 5000 }); } catch { /* already gone */ }
    if (this.proc && this.proc.exitCode === null) {
      await new Promise((r) => setTimeout(r, 1500));
      if (this.proc.exitCode === null) {
        if (process.platform === "win32") await run("taskkill", ["/PID", String(this.proc.pid), "/T", "/F"]);
        else this.proc.kill("SIGTERM");
      }
    }
    if (this.mode === "container" && this.engine) await run(this.engine, ["stop", "-t", "5", CONTAINER]);
  }
}

module.exports = { Backend };
