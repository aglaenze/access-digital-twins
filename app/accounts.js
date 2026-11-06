// Accounts of the students, on this computer: accounts.json in the folder of the app's data (userData).
// A password is never stored: only a salted scrypt hash. The account identifies the student (name, email) in the
// work handed in; it is not a protection against someone who controls this computer.
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

class Accounts {
  constructor(dir) {
    this.file = path.join(dir, "accounts.json");
  }

  load() {
    try {
      return JSON.parse(fs.readFileSync(this.file, "utf-8"));
    } catch {
      return { users: {} };
    }
  }

  save(db) {
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
    fs.writeFileSync(this.file + ".tmp", JSON.stringify(db, null, 1));
    fs.renameSync(this.file + ".tmp", this.file);
  }

  static id(email) {
    return String(email || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);
  }

  static hash(password, salt) {
    return crypto.scryptSync(password, salt, 32).toString("hex");
  }

  create({ name, email, password }) {
    name = String(name || "").trim();
    email = String(email || "").trim();
    if (name.length < 2) return { error: "Please write your full name." };
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return { error: "This email address does not look right." };
    if (String(password || "").length < 8) return { error: "The password needs at least 8 characters." };
    const db = this.load();
    const id = Accounts.id(email);
    if (db.users[id]) return { error: "An account with this email exists already on this computer: sign in." };
    const salt = crypto.randomBytes(16).toString("hex");
    const recovery = Accounts.recoveryCode();
    const rsalt = crypto.randomBytes(16).toString("hex");
    db.users[id] = { id, name, email, salt, hash: Accounts.hash(password, salt),
                     rsalt, rhash: Accounts.hash(recovery, rsalt),
                     created: new Date().toISOString(), last: new Date().toISOString() };
    this.save(db);
    return { user: this.public(db.users[id]), recovery };
  }

  signIn({ email, password }) {
    const db = this.load();
    const u = db.users[Accounts.id(email)];
    if (!u) return { error: "No account with this email on this computer. Create one." };
    const h = Accounts.hash(String(password || ""), u.salt);
    if (!crypto.timingSafeEqual(Buffer.from(h, "hex"), Buffer.from(u.hash, "hex"))) {
      return { error: "Wrong password." };
    }
    u.last = new Date().toISOString();
    this.save(db);
    return { user: this.public(u) };
  }

  // The recovery code: shown once at the creation of the account, to choose a new password if it is forgotten (the
  // accounts are on this computer: there is no email to reset it). Only its hash is kept.
  static recoveryCode() {
    const abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";              // no 0/O, 1/I: easy to copy
    const b = crypto.randomBytes(12);
    let s = "";
    for (let i = 0; i < 12; i++) s += abc[b[i] % abc.length] + (i % 4 === 3 && i < 11 ? "-" : "");
    return s;
  }

  reset({ email, code, password }) {
    const db = this.load();
    const u = db.users[Accounts.id(email)];
    const clean = String(code || "").toUpperCase().replace(/[^A-Z0-9]/g, "").replace(/(.{4})(?=.)/g, "$1-");
    if (!u || !u.rhash) return { error: "No account with this email on this computer." };
    const h = Accounts.hash(clean, u.rsalt);
    if (!crypto.timingSafeEqual(Buffer.from(h, "hex"), Buffer.from(u.rhash, "hex"))) {
      return { error: "This recovery code is not right." };
    }
    if (String(password || "").length < 8) return { error: "The new password needs at least 8 characters." };
    u.salt = crypto.randomBytes(16).toString("hex");
    u.hash = Accounts.hash(password, u.salt);
    u.last = new Date().toISOString();
    this.save(db);
    return { user: this.public(u) };
  }

  get(id) {
    const u = this.load().users[id];
    return u ? this.public(u) : null;
  }

  recent(n = 4) {
    return Object.values(this.load().users).sort((a, b) => (b.last || "").localeCompare(a.last || ""))
      .slice(0, n).map((u) => this.public(u));
  }

  public(u) {
    return { id: u.id, name: u.name, email: u.email };
  }
}

module.exports = { Accounts };
