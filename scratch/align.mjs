// Word timings for a recording, so subtitles land on the words rather than on
// a proportional guess.
//
// This is forced alignment, not transcription: the words are already known,
// they come from the script that was read. whisper only has to say roughly
// when each one was said. What it hears is allowed to be wrong — "bridge" for
// "ridge", "a fruit" for "as root" — because the script, not the transcript,
// is what ends up on screen. The two are lined up against each other and the
// script takes the timings.
//
// Results are cached under out/align, keyed by the recording and the text, so
// re-running costs nothing until one of them changes.

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
  writeFileSync,
  rmSync,
} from "node:fs";
import { dirname, join } from "node:path";

import { fileURLToPath } from "node:url";

// Paths are anchored to this file, not to the working directory, so the scripts
// run the same from scratch/ or anywhere else.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

const MODEL =
  process.env.WHISPER_MODEL ?? join(HERE, "models/ggml-base.en.bin");
const CACHE = join(HERE, "out/align");

// The alignment-head preset whisper.cpp needs, from the model file name.
const presetOf = (model) =>
  model.match(/ggml-([a-z0-9.]+)\.bin$/)?.[1] ?? "base.en";

export const available = () => existsSync(MODEL);

const DIGITS = [
  "zero",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
  "twelve",
  "thirteen",
  "fourteen",
  "fifteen",
  "sixteen",
  "seventeen",
  "eighteen",
  "nineteen",
  "twenty",
];

const normalize = (word) =>
  word
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "")
    .replace(/\d+/g, (n) => DIGITS[Number(n)] ?? n);

// How alike two words are, 0 to 1, by edit distance over their length.
function similarity(a, b) {
  if (!a.length || !b.length) return 0;
  if (a === b) return 1;
  const rows = a.length + 1;
  const cols = b.length + 1;
  let previous = Array.from({ length: cols }, (_, j) => j);
  for (let i = 1; i < rows; i++) {
    const current = [i];
    for (let j = 1; j < cols; j++) {
      current[j] = Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
    previous = current;
  }
  return 1 - previous[cols - 1] / Math.max(a.length, b.length);
}

// Ask whisper what it hears, and when.
function transcribe(audio, workDir) {
  const wav = join(workDir, "16k.wav");
  // whisper.cpp wants 16 kHz mono PCM whatever the recording arrived as.
  execFileSync("ffmpeg", [
    "-hide_banner",
    "-loglevel",
    "error",
    "-y",
    "-i",
    audio,
    "-ar",
    "16000",
    "-ac",
    "1",
    "-c:a",
    "pcm_s16le",
    wav,
  ]);

  const stem = join(workDir, "words");
  execFileSync(
    "whisper-cli",
    [
      "-m",
      MODEL,
      "-f",
      wav,
      // Token-level timings come from dynamic time warping, which the build
      // turns off whenever flash attention is on.
      "-dtw",
      presetOf(MODEL),
      "-nfa",
      // One word per segment, rather than one phrase.
      "-ml",
      "1",
      "-sow",
      "-oj",
      "-ojf",
      "-of",
      stem,
      "-np",
      "-nt",
    ],
    { stdio: ["ignore", "ignore", "ignore"] },
  );

  const parsed = JSON.parse(readFileSync(`${stem}.json`, "utf8"));
  const heard = [];
  for (const piece of parsed.transcription ?? []) {
    const token = piece.tokens?.[0];
    const centiseconds = token?.t_dtw ?? -1;
    const seconds =
      centiseconds >= 0
        ? centiseconds / 100
        : (piece.offsets?.from ?? 0) / 1000;
    const word = normalize(piece.text ?? "");
    if (word) heard.push({ word, at: seconds });
  }
  return heard;
}

// Line the script up against what whisper heard.
//
// Needleman-Wunsch over the two word sequences: a mis-heard word still matches
// its neighbour positionally, and a word whisper dropped or invented becomes a
// gap rather than dragging everything after it out of step.
const GAP = 0.6;

function align(script, heard) {
  const n = script.length;
  const m = heard.length;
  const score = Array.from({ length: n + 1 }, () => new Float64Array(m + 1));
  for (let i = 1; i <= n; i++) score[i][0] = -i * GAP;
  for (let j = 1; j <= m; j++) score[0][j] = -j * GAP;

  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      const pair =
        score[i - 1][j - 1] +
        (similarity(script[i - 1], heard[j - 1].word) - 0.4);
      score[i][j] = Math.max(
        pair,
        score[i - 1][j] - GAP,
        score[i][j - 1] - GAP,
      );
    }
  }

  const times = new Array(n).fill(null);
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    const pair =
      score[i - 1][j - 1] +
      (similarity(script[i - 1], heard[j - 1].word) - 0.4);
    if (score[i][j] === pair) {
      times[i - 1] = heard[j - 1].at;
      i--;
      j--;
    } else if (score[i][j] === score[i - 1][j] - GAP) {
      i--;
    } else {
      j--;
    }
  }
  return times;
}

// Words whisper never matched get a time between the ones around them, so a
// cue boundary is never left without one.
function fillGaps(times, duration) {
  const filled = [...times];
  const known = filled
    .map((t, i) => (t === null ? -1 : i))
    .filter((i) => i >= 0);
  if (!known.length)
    return filled.map((_, i) => (duration * i) / filled.length);

  for (let i = 0; i < filled.length; i++) {
    if (filled[i] !== null) continue;
    const before = known.filter((k) => k < i).pop();
    const after = known.find((k) => k > i);
    if (before === undefined) filled[i] = (filled[after] * i) / after;
    else if (after === undefined)
      filled[i] =
        filled[before] +
        ((duration - filled[before]) * (i - before)) / (filled.length - before);
    else
      filled[i] =
        filled[before] +
        ((filled[after] - filled[before]) * (i - before)) / (after - before);
  }
  // Timings must not go backwards, whatever the alignment did.
  for (let i = 1; i < filled.length; i++)
    if (filled[i] < filled[i - 1]) filled[i] = filled[i - 1];
  return filled;
}

// A highlight that arrives with the word reads as late. Landing it slightly
// ahead is what a reader following along expects.
const LINE_LEAD = 0.25;

// How much of the script a take actually covers.
//
// Counting how far into the script a match lands does not work: a four-second
// fragment of a long paragraph can still throw one stray match near the end and
// look complete. What matters is how many of the script's words are present in
// the recording at all.
const COVERAGE_VERSION = 2;

export function coverage(id, audio, text) {
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length) return null;

  const info = statSync(audio);
  const key = createHash("sha256")
    .update(
      `${audio}:${info.size}:${info.mtimeMs}:${text}:${MODEL}:v${COVERAGE_VERSION}`,
    )
    .digest("hex")
    .slice(0, 16);
  const cached = join(CACHE, `${id}.coverage.json`);
  if (existsSync(cached)) {
    const previous = JSON.parse(readFileSync(cached, "utf8"));
    if (previous.key === key) return previous.value;
  }

  const workDir = join(CACHE, `coverage-${id}`);
  mkdirSync(workDir, { recursive: true });
  let value;
  try {
    const heard = transcribe(audio, workDir);
    const times = align(words.map(normalize), heard);
    const reached = times.filter((t) => t !== null).length;
    value = { reached, words: words.length, ratio: reached / words.length };
  } finally {
    rmSync(workDir, { recursive: true, force: true });
  }

  mkdirSync(CACHE, { recursive: true });
  writeFileSync(cached, JSON.stringify({ key, value }));
  return value;
}

// When each line of a block of verse begins, from the recording of it.
export function lineTimes(id, audio, lines, duration) {
  const times = wordTimes(id, audio, lines.join(" "), duration);
  const starts = [];
  let at = 0;
  for (const line of lines) {
    starts.push(Math.max(0, (times[at] ?? duration) - LINE_LEAD));
    at += line.split(/\s+/).filter(Boolean).length;
  }
  return starts;
}

// One time per word of the script, in seconds from the start of the recording.
export function wordTimes(id, audio, text, duration) {
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length) return [];

  const info = statSync(audio);
  const key = createHash("sha256")
    .update(`${audio}:${info.size}:${info.mtimeMs}:${text}:${MODEL}`)
    .digest("hex")
    .slice(0, 16);
  const cached = join(CACHE, `${id}.json`);
  if (existsSync(cached)) {
    const previous = JSON.parse(readFileSync(cached, "utf8"));
    if (previous.key === key) return previous.times;
  }

  const workDir = join(CACHE, `work-${id}`);
  mkdirSync(workDir, { recursive: true });
  let times;
  try {
    const heard = transcribe(audio, workDir);
    times = fillGaps(align(words.map(normalize), heard), duration);
  } finally {
    rmSync(workDir, { recursive: true, force: true });
  }

  mkdirSync(CACHE, { recursive: true });
  writeFileSync(cached, JSON.stringify({ key, times }));
  return times;
}
