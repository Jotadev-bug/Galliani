// Checks the built site in dist/ before it is deployed (spec 016 Tests, R6, R11-R13).
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { gzipSync } from "node:zlib";

const DIST = new URL("../dist/", import.meta.url).pathname.replace(/^\/(\w:)/, "$1");
const ALLOWED = [
  "https://github.com/Jotadev-bug/Galliani",
  "https://api.github.com", // R8, and the CSP connect-src
  "https://openrouter.ai/keys",
  "https://jotadev-bug.github.io/Galliani/", // canonical and Open Graph URLs
];
const MAX_VIDEO = 8 * 1024 * 1024; // R12
const MAX_FIRST_LOAD = 500 * 1024; // R13: everything except the video
const errors = [];

const files = [];
const walk = (dir) => readdirSync(dir).forEach((f) => (statSync(join(dir, f)).isDirectory() ? walk(join(dir, f)) : files.push(join(dir, f))));
walk(DIST);

let firstLoad = 0;
for (const file of files) {
  const rel = relative(DIST, file).replaceAll("\\", "/");
  const size = statSync(file).size;
  if (/\.(mp4|webm)$/.test(rel)) {
    if (size > MAX_VIDEO) errors.push(`${rel} is ${(size / 1048576).toFixed(1)} MB, over the 8 MB limit`);
  } else if (!/^(og-image|privacy)/.test(rel) && !rel.startsWith("assets/privacy")) {
    // GitHub Pages serves text gzipped, so count what is actually transferred.
    firstLoad += /\.(html|js|css|svg)$/.test(rel) ? gzipSync(readFileSync(file)).length : size;
  }
  if (!/\.(html|js|css)$/.test(rel)) continue;
  const text = readFileSync(file, "utf8");
  // Only absolute URLs that the page can load or link to; skip XML namespaces and comments in libraries.
  for (const [, url] of text.matchAll(/(?:src|href|content|url\(|fetch\()\s*=?\s*["'(]?(https?:\/\/[^"')\s`]+)/g)) {
    if (!ALLOWED.some((a) => url.startsWith(a))) errors.push(`${rel}: external URL not allowed: ${url}`);
  }
  if (rel.endsWith(".html")) {
    if (!/^<!doctype html>/i.test(text)) errors.push(`${rel}: missing <!doctype html>`);
    if (!/<html lang="/.test(text)) errors.push(`${rel}: missing lang attribute`);
    if (!text.includes("Content-Security-Policy")) errors.push(`${rel}: missing Content-Security-Policy`);
  }
}
// Images are rendered by React, so check alt in the source instead.
const srcDir = new URL("../src/", import.meta.url).pathname.replace(/^\/(\w:)/, "$1");
for (const f of readdirSync(srcDir).filter((f) => f.endsWith(".tsx"))) {
  for (const [tag] of readFileSync(join(srcDir, f), "utf8").matchAll(/<(?:motion\.)?img\b[^>]*>/gs)) {
    if (!/\balt=/.test(tag)) errors.push(`src/${f}: <img> without alt`);
  }
}
if (firstLoad > MAX_FIRST_LOAD) errors.push(`home page assets are ${(firstLoad / 1024).toFixed(0)} KB, over the 500 KB limit`);

console.log(`Checked ${files.length} files; first-load assets ${(firstLoad / 1024).toFixed(0)} KB transferred.`);
if (errors.length) {
  errors.forEach((e) => console.error(`ERROR ${e}`));
  process.exit(1);
}
console.log("Site checks passed.");
