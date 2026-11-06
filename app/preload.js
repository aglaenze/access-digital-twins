// What the shell (shell/app.js) may ask the main process (main.js).
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("twins", {
  status: () => ipcRenderer.invoke("status"),
  session: () => ipcRenderer.invoke("session"),
  hasAccounts: () => ipcRenderer.invoke("has-accounts"),
  resume: () => ipcRenderer.invoke("resume"),
  createAccount: (form) => ipcRenderer.invoke("create-account", form),
  signIn: (form) => ipcRenderer.invoke("sign-in", form),
  resetPassword: (form) => ipcRenderer.invoke("reset-password", form),
  signOut: () => ipcRenderer.invoke("sign-out"),
  api: (method, path, body) => ipcRenderer.invoke("api", method, path, body),
  closeNotebook: (path) => ipcRenderer.invoke("close-notebook", path),
  handIn: () => ipcRenderer.invoke("hand-in"),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  on: (channel, fn) => {
    if (["status", "open-url", "before-quit"].includes(channel)) ipcRenderer.on(channel, (_e, ...a) => fn(...a));
  },
});
