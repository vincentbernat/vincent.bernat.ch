// Measures how much of its script each existing take reached, filling the cache
// the recorder reads. New takes are measured as they are saved; this is for the
// ones recorded before that existed.
//
//   node scratch/coverage.mjs

import { readFileSync, readdirSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import * as align from "./align.mjs";

import { fileURLToPath } from "node:url";

// Paths are anchored to this file, not to the working directory, so the scripts
// run the same from scratch/ or anywhere else.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

const TAKES = join(HERE, "audio/takes");
const CACHE = join(TAKES, "coverage.json");

if (!align.available()) {
  console.error("no whisper model");
  process.exit(1);
}

const data = JSON.parse(readFileSync(join(HERE, "out/segments.json"), "utf8"));
const known = existsSync(CACHE) ? JSON.parse(readFileSync(CACHE, "utf8")) : {};

// One take, for the server to run as a child process: whisper is synchronous
// and would otherwise hold up every other request while it thinks.
const only = process.argv.includes("--take")
  ? process.argv[process.argv.indexOf("--take") + 1]
  : null;

let done = 0;
let short = 0;
for (const file of readdirSync(TAKES)) {
  const match = file.match(/^(.+)\.take(\d+)\.mp3$/);
  if (!match) continue;
  const key = `${match[1]}.take${match[2]}`;
  if (only && key !== only) continue;
  const segment = data.segments.find((s) => s.slug === match[1]);
  if (!segment?.text) continue;
  const value = align.coverage(key, join(TAKES, file), segment.text);
  known[key] = value;
  writeFileSync(CACHE, JSON.stringify(known, null, 2));
  done++;
  if (value.ratio < 0.9) {
    short++;
    console.log(
      `  ${key}  ${(value.ratio * 100).toFixed(0)}% (${value.reached}/${value.words})`,
    );
  }
  process.stdout.write(`\r${done} measured, ${short} incomplete`);
}
writeFileSync(CACHE, JSON.stringify(known, null, 2));
console.log(`\n${done} takes measured, ${short} incomplete`);
