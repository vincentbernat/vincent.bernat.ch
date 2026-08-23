#!/usr/bin/env node
// The whole thing in one command: cue sheet, code blocks, a look at the
// narration, then the render and the join.
//
//   node pipeline.mjs --all
//   node pipeline.mjs --section electing-the-root-bridge
//   node pipeline.mjs --all --check     run the narration check and stop
//   node pipeline.mjs --all --no-check  render without it
//
// Every step is still its own script and can be run alone. This puts them in
// order and stops before an hour of rendering when a take no longer matches the
// script it was read from, since that is fixed in the browser, not here.

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "out");
const AUDIO = process.env.AUDIO_DIR ?? join(HERE, "audio");
const TAKES = join(AUDIO, "takes");
const STAGE_PORT = Number(process.env.STAGE_PORT ?? 8081);
const CDP_PORT = Number(process.env.MSTP_CDP_PORT ?? 9222);
// The share of its script a take has to reach. Below it, the reading stopped
// early. Same figure as coverage.mjs and the recorder page.
const COVERED = 0.9;

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
// Anything that is not ours belongs to record.mjs and assemble.mjs. Neither
// minds a flag meant for the other.
const passed = args.filter((a) => a !== "--check" && a !== "--no-check");

if (!passed.some((a) => ["--all", "--segment", "--section"].includes(a))) {
  console.error(
    "usage: node pipeline.mjs (--all | --segment <id|slug> | --section <slug>)" +
      " [--check] [--no-check]",
  );
  process.exit(1);
}

function step(title, command, argv) {
  console.log(`\n\x1b[1m== ${title}\x1b[0m`);
  const { status, error } = spawnSync(command, argv, {
    stdio: "inherit",
    cwd: HERE,
  });
  if (error) {
    console.error(`${title}: ${error.message}`);
    process.exit(1);
  }
  if (status !== 0) process.exit(status ?? 1);
}

function readJson(file) {
  try {
    return JSON.parse(readFileSync(file, "utf8"));
  } catch {
    return {};
  }
}

async function answers(url) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

// -- is the narration still the narration? -----------------------------

const stamp = (text) =>
  createHash("sha256").update(text).digest("hex").slice(0, 12);

const stemOf = (file) => file.replace(/^\d+-/, "").replace(/\.[^.]+$/, "");

// serve.mjs keeps the take a segment uses in selected.json. Without an entry
// there, the newest one on disk is the one in play.
function takeOf(slug, selected, takes) {
  if (selected[slug] !== undefined) return selected[slug];
  const numbers = takes
    .map((f) => f.match(new RegExp(`^${slug}\\.take(\\d+)\\.`)))
    .filter(Boolean)
    .map((m) => Number(m[1]));
  return numbers.length ? Math.max(...numbers) : null;
}

// The same three things the recorder page marks in its sidebar, read from the
// same files: a segment nobody has read, a take read from an older wording, a
// take that stopped before the end of its script.
function narrationTrouble() {
  const data = JSON.parse(readFileSync(join(OUT, "segments.json"), "utf8"));
  const scripts = readJson(join(TAKES, "scripts.json"));
  const coverage = readJson(join(TAKES, "coverage.json"));
  const selected = readJson(join(TAKES, "selected.json"));
  const files = existsSync(AUDIO) ? readdirSync(AUDIO) : [];
  const takes = existsSync(TAKES) ? readdirSync(TAKES) : [];

  const trouble = [];
  const spoken = new Set();
  for (const segment of data.segments) {
    // Cut, or carrying its own recording, or a card that says nothing.
    if (segment.skip || segment.audio || !segment.text?.trim()) continue;
    const file = files.find((f) => stemOf(f) === segment.slug);
    if (!file) {
      trouble.push([segment, "nothing recorded"]);
      continue;
    }
    spoken.add(segment.slug);
    const take = takeOf(segment.slug, selected, takes);
    if (take === null) continue;
    const key = `${segment.slug}.take${take}`;
    // Takes from before the stamp existed have nothing to compare against.
    const was = scripts[key];
    if (was !== undefined && was !== stamp(segment.text))
      trouble.push([segment, "script changed since it was read"]);
    const reach = coverage[key];
    if (reach && reach.ratio < COVERED)
      trouble.push([
        segment,
        `cut short, ${reach.reached} of ${reach.words} words`,
      ]);
  }

  // A recording whose paragraph moved or went away. It costs nothing at
  // assembly, but it is a sign the article shifted under the narration.
  const orphans = files
    .filter((f) => /\.(mp3|wav|flac|ogg|m4a|opus)$/i.test(f))
    .map(stemOf)
    .filter(
      (slug) =>
        !spoken.has(slug) && !data.segments.some((s) => s.slug === slug),
    );

  return { trouble, orphans };
}

// -- the pipeline ------------------------------------------------------

step("cue sheet and scripts", "node", ["extract.mjs"]);
step("code blocks", "python3", ["highlight.py"]);

console.log("\n\x1b[1m== narration\x1b[0m");
const { trouble, orphans } = narrationTrouble();
for (const slug of orphans) console.log(`  orphan recording: ${slug}`);
for (const [segment, why] of trouble)
  console.log(`  ${segment.id} ${segment.slug.padEnd(40)} ${why}`);
if (!trouble.length && !orphans.length) console.log("  every segment is read");

if (trouble.length && !flag("--no-check")) {
  console.error(
    `\n${trouble.length} segment(s) to see to. Fix them at` +
      ` http://127.0.0.1:${STAGE_PORT}/record-audio.html, then run this again.` +
      "\n--no-check renders without them: a missing take becomes silence of" +
      " the estimated length.",
  );
  process.exit(2);
}

if (flag("--check")) process.exit(0);

const missing = [];
if (!(await answers(`http://127.0.0.1:${STAGE_PORT}/out/segments.json`)))
  missing.push(`  the stage, on port ${STAGE_PORT}:  node serve.mjs`);
if (!(await answers(`http://127.0.0.1:${CDP_PORT}/json/version`)))
  missing.push(`  the browser, on port ${CDP_PORT}:  sh browser.sh`);
if (missing.length) {
  console.error("\nnot running, and the render needs both:");
  for (const line of missing) console.error(line);
  process.exit(1);
}

step("render", "node", ["record.mjs", ...passed]);
step("assemble", "node", ["assemble.mjs", ...passed]);
