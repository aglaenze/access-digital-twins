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
    db.users[id] = { id, name, email, salt, hash: Accounts.hash(password, salt),
                     created: new Date().toISOString(), last: new Date().toISOString() };
    this.save(db);
    return { user: this.public(db.users[id]) };
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
