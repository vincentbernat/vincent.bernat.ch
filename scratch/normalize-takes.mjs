// Gives every take already on disk the same lead-in as a fresh one.
//
//   node normalize-takes.mjs [--dry-run]
//
// Takes recorded before the lead-in was normalised start anywhere between a
// tenth of a second and a full second of room tone, and takes from the API
// start on the first syllable. The cue fires with the first frame of video, so
// that difference shows up as the diagram moving ahead of the words by a
// varying amount. This cuts whatever silence a take opens with and puts back a
// fixed lead.

import { execFileSync, spawnSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  unlinkSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const AUDIO_DIR = process.env.AUDIO_DIR ?? join(HERE, "audio");
const TAKES_DIR = join(AUDIO_DIR, "takes");
const SELECTED = join(TAKES_DIR, "selected.json");
const BITRATE = process.env.AUDIO_BITRATE ?? "128k";
const LEAD = Number(process.env.AUDIO_LEAD ?? 0.15);
const TOLERANCE = 0.03;

const dry = process.argv.includes("--dry-run");

const isAudio = (file) => /\.(mp3|wav|m4a|flac|ogg|opus)$/.test(file);
const slugOf = (file) => file.replace(/^\d+-/, "").replace(/\.[^.]+$/, "");
const takeOf = (file) => Number(file.match(/\.take(\d+)\./)?.[1] ?? 0);
// A take is named after the bare slug, with no number in front, so the number
// stripping slugOf does would eat the start of a slug that begins with a digit
// — "1-the-lowest-root-bridge-identifier-2" is one.
const takeSlug = (file) => file.replace(/\.take\d+\.[^.]+$/, "");

// How much silence a file opens with. silencedetect reports every quiet run,
// and only one starting at zero is a lead-in: a first report further in means
// the file already starts on sound.
function leadingSilence(file) {
  // silencedetect reports on stderr, so stdout would be empty.
  const { stderr: out } = spawnSync(
    "ffmpeg",
    [
      "-hide_banner",
      "-nostats",
      "-i",
      file,
      "-af",
      "silencedetect=noise=-40dB:d=0.01",
      "-f",
      "null",
      "-",
    ],
    { encoding: "utf8" },
  );
  const start = out.match(/silence_start: ([0-9.]+)/);
  const end = out.match(/silence_end: ([0-9.]+)/);
  if (!start || Number(start[1]) > 0.001) return 0;
  return end ? Number(end[1]) : 0;
}

function rewrite(file) {
  const spare = `${file}.trimming`;
  execFileSync("ffmpeg", [
    "-hide_banner",
    "-loglevel",
    "error",
    "-y",
    "-i",
    file,
    "-af",
    "silenceremove=start_periods=1:start_duration=0:start_threshold=-40dB:detection=peak," +
      `adelay=${Math.round(LEAD * 1000)}:all=1,` +
      "asetpts=N/SR/TB",
    "-codec:a",
    "libmp3lame",
    "-b:a",
    BITRATE,
    "-ac",
    "1",
    "-f",
    "mp3",
    spare,
  ]);
  renameSync(spare, file);
}

if (!existsSync(TAKES_DIR)) {
  console.log(`no takes under ${TAKES_DIR}`);
  process.exit(0);
}

const selected = existsSync(SELECTED)
  ? JSON.parse(readFileSync(SELECTED, "utf8"))
  : {};
const files = readdirSync(TAKES_DIR).filter(isAudio).sort();
const active = readdirSync(AUDIO_DIR).filter(isAudio);

let changed = 0;
let left = 0;
for (const file of files) {
  const path = join(TAKES_DIR, file);
  const was = leadingSilence(path);
  if (Math.abs(was - LEAD) <= TOLERANCE) {
    left++;
    continue;
  }
  console.log(
    `${file}  ${was.toFixed(3)}s -> ${LEAD.toFixed(2)}s${dry ? "  (dry run)" : ""}`,
  );
  if (dry) {
    changed++;
    continue;
  }
  rewrite(path);
  changed++;

  // The chosen take is copied into audio/, and that copy is what the pipeline
  // reads, so it has to follow.
  const slug = takeSlug(file);
  if (selected[slug] === takeOf(file)) {
    const copy = active.find((name) => slugOf(name) === slug);
    if (copy) copyFileSync(path, join(AUDIO_DIR, copy));
  }
}

console.log(
  `${changed} take${changed === 1 ? "" : "s"} ${dry ? "would be normalised" : "normalised"}, ${left} already at ${LEAD.toFixed(2)}s`,
);
