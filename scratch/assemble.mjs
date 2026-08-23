// Turns rendered frames plus narration into the finished video.
//
//   node scratch/assemble.mjs                    everything
//   node scratch/assemble.mjs --section security
//   node scratch/assemble.mjs --segment 042
//
// Each segment becomes its own mp4 with its own audio, then they are joined.
// A segment with no recording yet gets silence for as long as the script says
// it should take, so a full silent cut can be watched before a word is read.

import { execFileSync, spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  readdirSync,
} from "node:fs";
import { basename, dirname, join } from "node:path";
import { splitSentences } from "./text.mjs";
import { planRuns } from "./runs.mjs";
import * as align from "./align.mjs";

import { fileURLToPath } from "node:url";

// Paths are anchored to this file, not to the working directory, so the scripts
// run the same from scratch/ or anywhere else.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

const OUT = join(HERE, "out");
// What record.mjs produced: silent video for the segments that move, a single
// frame for the ones that do not.
const RAW = join(OUT, "clips-raw");
const STILLS = join(OUT, "stills");
const CLIPS = join(OUT, "clips");
const AUDIO = process.env.AUDIO_DIR ?? join(HERE, "audio");

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const value = (name) => {
  const i = args.indexOf(name);
  return i < 0 ? null : args[i + 1];
};

const data = JSON.parse(readFileSync(join(HERE, "out/segments.json"), "utf8"));
const manifest = JSON.parse(readFileSync(join(OUT, "render.json"), "utf8"));
const FPS = data.fps;
const PRESET = process.env.X264_PRESET ?? "veryfast";
const CRF = process.env.X264_CRF ?? "12";
// True-peak ceiling, in dBFS.
const PEAK = process.env.AUDIO_PEAK ?? "-2.0";
const GAP = data.segmentGap ?? 0.45;
// A quiet bed under the whole video. It loops, so a short piece is fine.
const MUSIC =
  process.env.MUSIC ??
  join(HERE, "assets/aaron-dunn-sonatina-no-2-in-g-major.mp3");
// Where the bed sits, in LUFS. The narration sits at -16.
const MUSIC_LUFS = Number(process.env.MUSIC_LUFS ?? -40);
const MUSIC_FADE = 4;
// Half the level under the poem, reached over this many seconds.
const MUSIC_DUCK = 0.5;
const MUSIC_DUCK_FADE = 2;
// Lift for the finished mix, in dB. Segments are levelled one by one, which
// leaves the whole video below the ceiling rather than at it.
const LIFT = Number(process.env.AUDIO_GAIN ?? 2.5);

const ffmpeg = (params) =>
  execFileSync("ffmpeg", [
    "-hide_banner",
    "-loglevel",
    "error",
    "-y",
    ...params,
  ]);

const clock = (seconds) =>
  `${Math.floor(seconds / 60)}m${String(Math.round(seconds % 60)).padStart(2, "0")}s`;

// The same, for a call worth waiting minutes on. The join reads the whole video
// back and encodes its sound again, and says nothing at all on its own.
function ffmpegWatched(params, seconds) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      "ffmpeg",
      [
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-progress",
        "pipe:1",
        "-y",
        ...params,
      ],
      { stdio: ["ignore", "pipe", "inherit"] },
    );
    let rest = "";
    child.stdout.on("data", (chunk) => {
      const lines = (rest + chunk).split("\n");
      rest = lines.pop();
      for (const line of lines) {
        const at = line.match(/^out_time=(\d+):(\d\d):(\d\d)/);
        if (!at) continue;
        const done = Number(at[1]) * 3600 + Number(at[2]) * 60 + Number(at[3]);
        process.stdout.write(`\r  ${clock(done)} of ${clock(seconds)}`);
      }
    });
    child.on("error", reject);
    child.on("close", (code) => {
      process.stdout.write("\n");
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg left off with ${code}`));
    });
  });
}

// A fixed gain keeps the music as played. loudnorm would flatten it, which is
// the opposite of what a bed needs.
function musicGain(file) {
  const { stderr } = spawnSync(
    "ffmpeg",
    [
      "-hide_banner",
      "-nostats",
      "-i",
      file,
      "-af",
      "ebur128",
      "-f",
      "null",
      "-",
    ],
    { encoding: "utf8" },
  );
  const found = stderr?.match(/Integrated loudness:\s*\n\s*I:\s+(-?[\d.]+)/);
  if (!found) throw new Error(`cannot measure the loudness of ${file}`);
  return Number((MUSIC_LUFS - Number(found[1])).toFixed(2));
}

// Where the poem sits in the finished video. The bed drops under it so Radia
// stays in front.
function poemWindow(clips) {
  let at = 0;
  for (const { segment, seconds } of clips) {
    if (segment.visual.type === "poem") return [at, at + seconds];
    at += seconds;
  }
  return null;
}

function audioFor(segment) {
  if (segment.audio) return existsSync(segment.audio) ? segment.audio : null;
  if (!existsSync(AUDIO)) return null;
  // On the slug, not the number: renumbering must not orphan a recording.
  const match = readdirSync(AUDIO).find(
    (f) => f.replace(/^\d+-/, "").replace(/\.[^.]+$/, "") === segment.slug,
  );
  return match ? join(AUDIO, match) : null;
}

// How long this segment should last now, which may be less than it was
// rendered for once a recording replaces an estimate.
const durations = new Map();

function durationOf(segment) {
  // Asked for once when the runs are planned and again when the clip is built,
  // and every call is an ffprobe.
  if (durations.has(segment.slug)) return durations.get(segment.slug);
  const seconds = measure(segment) + (segment.tail ?? 0);
  durations.set(segment.slug, seconds);
  return seconds;
}

function probeDuration(file) {
  const out = execFileSync("ffprobe", [
    "-v",
    "error",
    "-show_entries",
    "format=duration",
    "-of",
    "default=noprint_wrappers=1:nokey=1",
    file,
  ]);
  return Number(String(out).trim());
}

function measure(segment) {
  if (segment.durationOverride) return segment.durationOverride;
  const audio = audioFor(segment);
  if (audio) return probeDuration(audio);
  if (segment.holdOverride) return segment.holdOverride;
  return segment.hold ?? segment.estimate ?? 3;
}

const { runOf } = planRuns(data.segments, durationOf, GAP);

// A recording made before its paragraph was edited would otherwise go unnoticed:
// the take is found by slug, and a slug only comes from the opening words.
let scriptStamps = null;
function scriptChanged(segment) {
  if (!scriptStamps) {
    try {
      scriptStamps = JSON.parse(
        readFileSync(join(AUDIO, "takes", "scripts.json"), "utf8"),
      );
    } catch {
      scriptStamps = {};
    }
  }
  let selected = {};
  try {
    selected = JSON.parse(
      readFileSync(join(AUDIO, "takes", "selected.json"), "utf8"),
    );
  } catch {
    return false;
  }
  const was = scriptStamps[`${segment.slug}.take${selected[segment.slug]}`];
  if (was === undefined) return false;
  return (
    was !== createHash("sha256").update(segment.text).digest("hex").slice(0, 12)
  );
}

function noSuchThing(what) {
  console.error(`no ${what}. Names come from out/segments.json.`);
  process.exit(2);
}

function selection() {
  if (value("--segment")) {
    const wanted = value("--segment");
    const picked = data.segments.filter(
      (s) => s.id === wanted || s.slug === wanted,
    );
    if (!picked.length) return noSuchThing(`segment "${wanted}"`);
    return picked;
  }
  if (value("--section")) {
    const wanted = value("--section");
    const picked = data.segments.filter((s) => s.sectionSlug === wanted);
    if (!picked.length) return noSuchThing(`section "${wanted}"`);
    return picked;
  }
  if (flag("--all")) return data.segments.filter((s) => !s.skip);
  console.error(
    "usage: assemble.mjs --all | --segment <id|slug> | --section <slug>",
  );
  console.error(
    "       --no-align  time subtitles by proportion, not by whisper",
  );
  process.exit(2);
}

// One segment -> one mp4 with its narration on it.
//
// A moving segment already has its video, gap included, so it is copied
// through untouched and only the audio is encoded. A still segment is one
// frame stretched to length here, which is why changing a recording costs
// nothing to re-render.
function buildClip(segment) {
  const entry = manifest[segment.slug];
  if (!entry) return null;
  entry.seconds_needed = durationOf(segment);
  const total = entry.seconds_needed + GAP;
  const clip = join(CLIPS, `${segment.slug}.mp4`);

  // A segment inside a continuous run has no clip of its own: its frames are a
  // window on the run's, cut out here. Moving time between the members of a run
  // therefore costs nothing to render.
  // What was rendered has to be what the plan now asks for. Slicing the wrong
  // clip, or reusing a segment's own clip after it joined a run, would put the
  // wrong frames on screen with nothing to say so.
  const member = runOf[segment.slug] ?? null;
  if ((entry.run ?? null) !== (member?.id ?? null)) {
    console.warn(
      `  ${segment.slug}: rendered ${entry.run ? `in run ${entry.run}` : "on its own"}, now ${member ? `in run ${member.id}` : "on its own"} — run record.mjs`,
    );
    return null;
  }
  const runClip = member ? join(RAW, `run-${member.id}.mp4`) : null;

  // A clip rendered longer than the segment now needs is cut down rather than
  // rendered again. record.mjs only allows that where the diagram is at rest,
  // so the cut never lands mid-animation. The tail pause has to be rebuilt,
  // which means this one clip is re-encoded instead of copied.
  const trimmed =
    !runClip && !entry.still && entry.seconds - entry.seconds_needed > 0.05;
  const video = runClip
    ? ["-i", runClip]
    : entry.still
      ? [
          "-loop",
          "1",
          "-framerate",
          String(FPS),
          "-t",
          String(total),
          "-i",
          join(STILLS, `${segment.slug}.png`),
        ]
      : trimmed
        ? [
            "-t",
            String(entry.seconds_needed),
            "-i",
            join(RAW, `${segment.slug}.mp4`),
          ]
        : ["-i", join(RAW, `${segment.slug}.mp4`)];

  const narration = audioFor(segment);
  const audio = narration
    ? ["-i", narration]
    : ["-f", "lavfi", "-t", String(total), "-i", "anullsrc=r=48000:cl=stereo"];

  const shape = narration
    ? `loudnorm=I=-16:TP=${PEAK}:LRA=11,aresample=48000,aformat=channel_layouts=stereo,apad`
    : "anull";

  ffmpeg([
    ...video,
    ...audio,
    "-filter_complex",
    runClip
      ? `[0:v]trim=start=${member.offset.toFixed(3)}:end=${(member.offset + total).toFixed(3)},setpts=PTS-STARTPTS[v];[1:a]${shape}[a]`
      : trimmed
        ? `[0:v]tpad=stop_mode=clone:stop_duration=${GAP}[v];[1:a]${shape}[a]`
        : `[1:a]${shape}[a]`,
    "-map",
    runClip || trimmed ? "[v]" : "0:v",
    "-map",
    "[a]",
    "-t",
    String(total),
    ...(entry.still || trimmed || runClip
      ? [
          "-c:v",
          "libx264",
          "-preset",
          PRESET,
          "-crf",
          CRF,
          "-pix_fmt",
          "yuv420p",
          "-r",
          String(FPS),
        ]
      : ["-c:v", "copy"]),
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-ar",
    "48000",
    "-ac",
    "2",
    "-movflags",
    "+faststart",
    clip,
  ]);
  // The length asked for and the length obtained are not the same: a video
  // stream ends on a frame boundary, so a clip is up to one frame longer than
  // total. Half a frame per clip, over a hundred clips, is enough to pull the
  // subtitles away from the voice by the end. Everything placed on the
  // timeline afterwards counts from the measured length instead.
  return { clip, seconds: probeDuration(clip) };
}

// -- subtitles ---------------------------------------------------------

// Roughly two lines of a comfortable reading width.
const CUE_CHARS = 84;
const LINE_CHARS = 44;
const MIN_CUE = 1.0;
// Longer than this and a cue has been on screen long enough to reread twice.
const MAX_CUE = 7.0;

// Break narration into subtitle-sized pieces.
//
// Where a cue ends is what makes subtitles easy or tiring to read. A sentence
// short enough to stand alone does. A longer one is divided into as few equal
// pieces as will fit, which avoids leaving a two-word orphan on screen, with a
// break after punctuation preferred and never on a word that leans on the one
// after it.

// Words that belong with what follows them, so a cue should not end on one.
const WEAK_ENDINGS = new Set([
  "a",
  "an",
  "the",
  "of",
  "to",
  "in",
  "on",
  "at",
  "for",
  "with",
  "and",
  "or",
  "but",
  "from",
  "by",
  "as",
  "is",
  "are",
  "was",
  "were",
  "that",
  "this",
  "these",
  "those",
  "its",
  "their",
  "his",
  "her",
  "our",
  "your",
  "no",
  "not",
  "than",
  "into",
  "over",
  "under",
  "between",
  "when",
  "while",
  "if",
  "so",
]);

const endsWeakly = (piece) => {
  const last = piece
    .split(" ")
    .pop()
    .replace(/[^\w']/g, "")
    .toLowerCase();
  return WEAK_ENDINGS.has(last);
};

function packWords(text, target) {
  const words = text.split(/\s+/).filter(Boolean);
  const pieces = [];
  let current = [];

  const flush = () => {
    if (current.length) pieces.push(current.join(" "));
    current = [];
  };

  for (const word of words) {
    const candidate = [...current, word].join(" ");
    if (candidate.length > target && current.length) {
      // Do not leave a word stranded from what it introduces.
      if (current.length > 1 && endsWeakly(current.join(" "))) {
        const moved = current.pop();
        flush();
        current = [moved, word];
      } else {
        flush();
        current = [word];
      }
    } else {
      current.push(word);
      // A clause ending near the target is a better break than the target.
      if (/[,;:—][")]?$/.test(word) && candidate.length >= target * 0.7)
        flush();
    }
  }
  flush();
  return pieces;
}

// Divide one sentence into exactly `parts` pieces.
//
// Packing greedily at len/parts overshoots whenever a break has to move back
// off a weak word, which leaves a two-word orphan at the end. Widening the
// target until the piece count comes out right costs nothing and removes them.
function splitSentence(sentence, parts) {
  const ideal = Math.ceil(sentence.length / parts);
  let best = packWords(sentence, ideal);
  for (
    let target = ideal + 1;
    target <= CUE_CHARS && best.length > parts;
    target++
  ) {
    best = packWords(sentence, target);
  }
  return best;
}

function cueTexts(text) {
  const cues = [];
  for (const sentence of splitSentences(text)) {
    if (sentence.length <= CUE_CHARS) {
      cues.push(sentence);
      continue;
    }
    const pieces = splitSentence(
      sentence,
      Math.ceil(sentence.length / CUE_CHARS),
    );
    // A stray short piece reads as a flicker. Fold it into a neighbour, but
    // only within this sentence: joining across a full stop reads worse.
    for (let i = 0; i < pieces.length && pieces.length > 1; i++) {
      if (pieces[i].length >= 24) continue;
      const room = CUE_CHARS + 12;
      const before = i > 0 ? pieces[i - 1].length : Infinity;
      const after = i < pieces.length - 1 ? pieces[i + 1].length : Infinity;
      if (before <= after && before + pieces[i].length + 1 <= room) {
        pieces[i - 1] = `${pieces[i - 1]} ${pieces[i]}`;
      } else if (after + pieces[i].length + 1 <= room) {
        pieces[i + 1] = `${pieces[i]} ${pieces[i + 1]}`;
      } else {
        continue;
      }
      pieces.splice(i, 1);
      i--;
    }
    cues.push(...pieces);
  }
  return cues;
}

// Two balanced lines, breaking after punctuation when there is a choice, so a
// cue never renders as one long line and one stray word.
function wrap(text) {
  if (text.length <= LINE_CHARS) return text;
  const words = text.split(" ");
  let best = null;
  for (let i = 1; i < words.length; i++) {
    const top = words.slice(0, i).join(" ");
    const bottom = words.slice(i).join(" ");
    if (top.length > LINE_CHARS + 6) break;
    if (bottom.length > LINE_CHARS + 6) continue;
    const punctuated = /[,;:.—]$/.test(top) ? -8 : 0;
    const score = Math.abs(top.length - bottom.length) + punctuated;
    if (!best || score < best.score)
      best = { score, text: `${top}\n${bottom}` };
  }
  return best ? best.text : text;
}

const stamp = (seconds) => {
  const ms = Math.max(0, Math.round(seconds * 1000));
  const h = String(Math.floor(ms / 3600000)).padStart(2, "0");
  const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, "0");
  const s = String(Math.floor((ms % 60000) / 1000)).padStart(2, "0");
  return `${h}:${m}:${s}.${String(ms % 1000).padStart(3, "0")}`;
};

// What is spoken over a segment, and when.
//
// With a recording in hand, whisper says when each word was said and the cues
// start on the right word. Without one — a segment not yet recorded, or
// alignment turned off — a cue instead takes a share of the segment in
// proportion to how much of the text it holds, which is close enough over the
// fourteen seconds or so a segment usually lasts.
function segmentCues(segment, start, seconds) {
  // The tail is diagram time after the words have stopped, so it is part of the
  // clip but not of the reading: counted here it would hold the last subtitle
  // on screen for the whole of it.
  const spoken = seconds - (segment.tail ?? 0);
  const speech = spoken - GAP > 0 ? spoken - GAP : spoken;

  if (segment.visual.type === "poem") {
    const lines = segment.visual.lines;
    const audio =
      segment.audio && existsSync(segment.audio) ? segment.audio : null;
    let marks = null;
    if (audio && align.available() && !args.includes("--no-align")) {
      try {
        marks = align.lineTimes(segment.slug, audio, lines, speech);
      } catch {
        marks = null;
      }
    }
    return lines.map((line, i) => {
      const from = marks?.[i] ?? (speech / lines.length) * i;
      const to = marks?.[i + 1] ?? speech;
      return {
        start: start + from,
        end: start + Math.min(Math.max(from + MIN_CUE, to), speech),
        text: line,
      };
    });
  }

  if (!segment.text) return [];

  const pieces = cueTexts(segment.text);
  const times = wordTimesFor(segment, speech);

  if (times) {
    const spans = [];
    let word = 0;
    for (const piece of pieces) {
      const count = piece.split(/\s+/).filter(Boolean).length;
      spans.push({ text: piece, first: word, count });
      word += count;
    }

    // Now that the real timings are known, a cue that turns out to sit on
    // screen too long is divided again, at the word nearest its middle.
    for (let i = 0; i < spans.length; i++) {
      const span = spans[i];
      const from = times[span.first] ?? 0;
      const to = times[span.first + span.count] ?? speech;
      if (to - from <= MAX_CUE || span.count < 4) continue;
      const middle = (from + to) / 2;
      let at = 1;
      for (let k = 1; k < span.count; k++)
        if (
          Math.abs(times[span.first + k] - middle) <
          Math.abs(times[span.first + at] - middle)
        )
          at = k;
      const words = span.text.split(/\s+/).filter(Boolean);
      spans.splice(
        i,
        1,
        { text: words.slice(0, at).join(" "), first: span.first, count: at },
        {
          text: words.slice(at).join(" "),
          first: span.first + at,
          count: span.count - at,
        },
      );
      i--;
    }

    // A cue must stay inside the clip it belongs to. It can fall outside when
    // the recording is longer than the segment was rendered for, which happens
    // whenever a take changes without record.mjs being re-run.
    const cues = [];
    for (const span of spans) {
      const from = Math.min(times[span.first] ?? 0, speech);
      const to = Math.min(times[span.first + span.count] ?? speech, speech);
      if (from >= speech) continue;
      cues.push({
        start: start + from,
        end: start + Math.min(Math.max(from + MIN_CUE, to), speech),
        text: wrap(span.text),
      });
    }
    // A minimum length can push a cue past the one after it.
    for (let i = 0; i < cues.length - 1; i++)
      if (cues[i].end > cues[i + 1].start) cues[i].end = cues[i + 1].start;
    return cues.filter((cue) => cue.end > cue.start);
  }

  const total = pieces.reduce((n, piece) => n + piece.length, 0) || 1;
  const cues = [];
  let at = start;
  for (const piece of pieces) {
    const span = Math.max(MIN_CUE, (piece.length / total) * speech);
    cues.push({ start: at, end: at + span, text: wrap(piece) });
    at += span;
  }
  const overrun = at - (start + speech);
  if (overrun > 0 && cues.length) {
    const shrink = speech / (speech + overrun);
    let cursor = start;
    for (const cue of cues) {
      const span = (cue.end - cue.start) * shrink;
      cue.start = cursor;
      cue.end = cursor + span;
      cursor += span;
    }
  }
  return cues;
}

let alignmentReported = false;

function wordTimesFor(segment, speech) {
  if (args.includes("--no-align")) return null;
  const audio = audioFor(segment);
  if (!audio || !align.available()) {
    if (!alignmentReported && !align.available()) {
      console.log("  no whisper model, subtitles timed by proportion");
      alignmentReported = true;
    }
    return null;
  }
  try {
    return align.wordTimes(segment.slug, audio, segment.text, speech);
  } catch (err) {
    console.warn(
      `  ${segment.id}: alignment failed (${err.message}), timing by proportion`,
    );
    return null;
  }
}

function writeSubtitles(clips, file) {
  const out = ["WEBVTT", ""];
  let at = 0;
  let count = 0;
  let done = 0;
  for (const { segment, seconds } of clips) {
    // A take whisper has not seen before takes seconds to line up, so say which
    // one is holding things up rather than sit there.
    process.stdout.write(
      `\r  ${++done}/${clips.length} subtitles  ${segment.slug.slice(0, 40).padEnd(40)}`,
    );
    for (const cue of segmentCues(segment, at, seconds)) {
      count++;
      out.push(
        String(count),
        `${stamp(cue.start)} --> ${stamp(cue.end)}`,
        cue.text,
        "",
      );
    }
    at += seconds;
  }
  process.stdout.write("\n");
  writeFileSync(file, out.join("\n"));
  return count;
}

// Chapter marks at every heading, so the finished file can be navigated. A
// chapter runs from its title card to the next one, not just over the card.
function chapters(clips) {
  const marks = [];
  let at = 0;
  for (const { segment, seconds } of clips) {
    if (segment.visual.type === "title") {
      if (marks.length) marks[marks.length - 1].end = at;
      marks.push({ start: at, end: at, title: segment.visual.title });
    }
    at += seconds;
  }
  if (marks.length) marks[marks.length - 1].end = at;

  const meta = [";FFMETADATA1"];
  for (const mark of marks) {
    meta.push(
      "[CHAPTER]",
      "TIMEBASE=1/1000",
      `START=${Math.round(mark.start * 1000)}`,
      `END=${Math.round(mark.end * 1000)}`,
      `title=${mark.title.replace(/[\\=;#\n]/g, " ")}`,
    );
  }
  return meta.join("\n") + "\n";
}

const chosen = selection().filter((s) => manifest[s.slug]);
if (!chosen.length) {
  console.error("nothing rendered yet: run scratch/record.mjs first");
  process.exit(1);
}

mkdirSync(CLIPS, { recursive: true });
const built = [];
const stale = [];
let missing = 0;
for (const segment of chosen) {
  const result = buildClip(segment);
  if (!result) continue;
  if (segment.text && !audioFor(segment)) missing++;
  if (segment.text && audioFor(segment) && scriptChanged(segment))
    stale.push(segment.slug);
  built.push({ segment, ...result });
  process.stdout.write(`\r  ${built.length}/${chosen.length} clips`);
}
console.log();

// The concat demuxer resolves relative paths against the list file, which sits
// in the same directory as the clips.
const list = built
  .map(({ segment }) => `file '${segment.slug}.mp4'`)
  .join("\n");
writeFileSync(join(CLIPS, "list.txt"), list + "\n");
writeFileSync(join(OUT, "chapters.txt"), chapters(built));

const name = value("--section") ?? value("--segment") ?? "spanning-tree";
const final = join(OUT, `${name}.mp4`);
const length = built.reduce((n, b) => n + b.seconds, 0);
// The ramps sit outside the poem, so the bed is already down when she starts.
const poem = poemWindow(built);
const r = MUSIC_DUCK_FADE;
const duck = poem
  ? `volume='1-${1 - MUSIC_DUCK}*clip(min((t-${Math.max(0, poem[0] - r).toFixed(3)})/${r},(${(poem[1] + r).toFixed(3)}-t)/${r}),0,1)':eval=frame,`
  : "";
// The bed is one input played on repeat, cut to the length of the video. amix
// would rescale both sides without normalize=0.
const graph =
  `[2:a]volume=${musicGain(MUSIC)}dB,` +
  duck +
  `afade=t=in:st=0:d=${MUSIC_FADE},` +
  `afade=t=out:st=${Math.max(0, length - MUSIC_FADE).toFixed(3)}:d=${MUSIC_FADE},` +
  "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[m];" +
  `[0:a][m]amix=inputs=2:duration=first:normalize=0,volume=${LIFT}dB[a]`;

console.log(
  `  joining ${built.length} clips into ${final}, ${clock(length)} of video`,
);
await ffmpegWatched(
  [
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    join(CLIPS, "list.txt"),
    "-i",
    join(OUT, "chapters.txt"),
    "-stream_loop",
    "-1",
    "-i",
    MUSIC,
    "-filter_complex",
    graph,
    "-map",
    "0:v",
    "-map",
    "[a]",
    // Metadata from the chapter file, not from the clips.
    "-map_metadata",
    "1",
    "-c:v",
    "copy",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-ar",
    "48000",
    "-ac",
    "2",
    final,
  ],
  length,
);

const vtt = join(OUT, `${name}.en.vtt`);
const cueCount = writeSubtitles(built, vtt);

console.log(`\n${final}`);
console.log(`${vtt} (${cueCount} cues)`);
console.log(`${built.length} segments, ${clock(length)}`);
console.log(
  `music: ${basename(MUSIC)} at ${MUSIC_LUFS} LUFS` +
    (poem ? ", half that under the poem" : "") +
    `, mix lifted by ${LIFT} dB`,
);
if (missing)
  console.log(
    `${missing} segment(s) still silent: no recording found in ${AUDIO}/`,
  );
if (stale.length) {
  console.log(
    `\n${stale.length} recording(s) predate a change to their script:`,
  );
  for (const slug of stale) console.log(`  ${slug}`);
}
