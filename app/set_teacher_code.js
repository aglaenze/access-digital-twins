// Sets the teacher code of the app (the teacher view of the catalogue: all exercises at all levels).
//   node set_teacher_code.js <code>
// Only a salted hash is written (teacher_code.json, shipped with the app): the code itself is never in the repository.
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { Accounts } = require("./accounts");
const code = String(process.argv[2] || "").trim();
if (code.length < 6) { console.error("Usage: node set_teacher_code.js <code of at least 6 characters>"); process.exit(1); }
const salt = crypto.randomBytes(16).toString("hex");
fs.writeFileSync(path.join(__dirname, "teacher_code.json"), JSON.stringify({ salt, hash: Accounts.hash(code, salt) }, null, 1) + "\n");
console.log("Teacher code set (teacher_code.json).");
