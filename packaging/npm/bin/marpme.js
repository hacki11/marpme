#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const https = require("node:https");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const manifestUrl = process.env.MARPME_RELEASE_MANIFEST || "https://github.com/hacki11/marpme/releases/latest/download/latest.json";
const architectures = { x64: "x86_64", arm64: "aarch64" };
const systems = { win32: "windows", linux: "linux" };
const key = `${systems[process.platform] || process.platform}-${architectures[process.arch] || process.arch}`;

function download(url, destination, redirects = 0) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { "User-Agent": "@company/marpme" } }, (response) => {
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location && redirects < 5) {
        response.resume();
        return download(new URL(response.headers.location, url), destination, redirects + 1).then(resolve, reject);
      }
      if (response.statusCode !== 200) {
        response.resume();
        return reject(new Error(`Download failed with HTTP ${response.statusCode}`));
      }
      if (typeof destination === "function") {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => { body += chunk; });
        response.on("end", () => { try { resolve(destination(body)); } catch (error) { reject(error); } });
      } else {
        const output = fs.createWriteStream(destination, { mode: 0o755 });
        response.pipe(output);
        output.on("finish", () => output.close(resolve));
        output.on("error", reject);
      }
    }).on("error", reject);
  });
}

(async () => {
  const manifest = await download(manifestUrl, JSON.parse);
  const artifact = manifest.artifacts && manifest.artifacts[key];
  if (!artifact || !artifact.url || !/^[a-fA-F0-9]{64}$/.test(artifact.sha256 || "")) {
    throw new Error(`Release manifest has no valid artifact for ${key}`);
  }
  const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "marpme-"));
  const executable = path.join(temporaryDirectory, process.platform === "win32" ? "marpme.exe" : "marpme");
  try {
    await download(artifact.url, executable);
    const digest = crypto.createHash("sha256").update(fs.readFileSync(executable)).digest("hex");
    if (digest.toLowerCase() !== artifact.sha256.toLowerCase()) throw new Error("Downloaded artifact failed SHA-256 verification");
    fs.chmodSync(executable, 0o755);
    const result = spawnSync(executable, process.argv.slice(2), {
      stdio: "inherit",
      env: { ...process.env, MARPME_EPHEMERAL: "1" }
    });
    if (result.error) throw result.error;
    process.exitCode = result.status === null ? 1 : result.status;
  } finally {
    fs.rmSync(temporaryDirectory, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(`marpme launcher: ${error.message}`);
  process.exitCode = 1;
});
