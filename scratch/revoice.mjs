#!/usr/bin/env node
//
// Replace the voice track of the network CMDB video with an ElevenLabs voice.
//
// The subtitles give both the text and the timing. Every cue is read on its
// own, then dropped back at the exact time it has in the subtitles. Starts
// stay where they are. Ends follow the voice, and a cue that runs long pushes
// the next one.
//
// One cue, one request. Reading several cues in one go and cutting them apart
// afterwards does not work: where the voice runs from one cue into the next
// without a pause, there is no silence to cut at, and the cut either clips the
// last word or leaves the start of the next one hanging at the end. The text
// around the cue is still sent, as context, so the tone carries over.
//
// Both languages are done at once, one voice track each, English first.
//
// Usage:
//
//   node scratch/revoice.mjs plan            list the cues
//   node scratch/revoice.mjs tts             synthesize the missing cues
//   node scratch/revoice.mjs build           assemble, mux, retime the subtitles
//   node scratch/revoice.mjs all             all of the above
//
// Options:
//
//   --lang fr        only that language, instead of every one of them
//   --redo 3,7-9     synthesize those cues again, even if cached
//   --redo all       synthesize everything again
//   --dry-run        with "tts": show what would be sent, send nothing
//
// Cue audio is cached under scratch/out/<lang>/tts, named after the cue, so a
// rerun only pays for what changed. When a word comes out wrong, fix it in the
// pronunciation dictionary, then redo the cues that contain it:
//
//   node scratch/revoice.mjs tts --redo 27 --lang fr
//   node scratch/revoice.mjs build
//
// The rebuilt video and the subtitle files land in scratch/out, the working
// files in scratch/out/<lang>. Subtitles keep their text and get the timings
// of the voice of their own language, which is why the two no longer share
// their timings.
//
// The result is a master: the video is copied over untouched, and the voice
// is encoded once, by ElevenLabs. Trimming the silence around a cue means
// decoding the MP3, so the track goes back into the file as FLAC. Encoding it
// again, to MP3 or to AAC, would be a second pass over audio that is already
// lossy. ELEVEN_FORMAT takes wav_44100 or wav_48000 for a lossless voice,
// which needs the Pro tier.
//
// Needs ELEVENLABS_API_KEY and ffmpeg.

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  rmSync,
  writeFileSync,
  writeSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Paths are anchored to this file, so the script runs the same from anywhere.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");
const MEDIA = join(REPO, "content/media/videos");
const STEM = "2021-network-cmdb";
const VIDEO = ["mkv", "mp4", "webm"]
  .map((extension) => join(MEDIA, `${STEM}.${extension}`))
  .find(existsSync);

// The cloned voice and the dictionary that fixes the technical words. Alias
// rules work with any model. Phoneme rules only work with eleven_turbo_v2 and
// eleven_flash_v2, so set ELEVEN_MODEL when the dictionary uses them.
const VOICE = "m2MRSLlg6HZtNmBXNyFO"; // my pro voice
const DICTIONARY = "JJkVw7kU7FwOZTDi5Feu"; // my custom dictionary
const ELEVEN_MODEL = process.env.ELEVEN_MODEL ?? "eleven_multilingual_v2";
const ELEVEN_FORMAT = process.env.ELEVEN_FORMAT ?? "mp3_44100_128";
// Cues are kept in the format they arrive in, and the track is built at their
// own sample rate, so the voice is never resampled.
const CONTAINER = ELEVEN_FORMAT.split("_")[0];
if (CONTAINER !== "wav" && CONTAINER !== "mp3")
  throw new Error(`ELEVEN_FORMAT must be wav_* or mp3_*, not ${ELEVEN_FORMAT}`);
const RATE = Number(ELEVEN_FORMAT.split("_")[1]);

// One voice track per language, in this order. English plays by default.
// Matroska wants the bibliographic ISO 639-2 code.
const LANGS = ["en", "fr"];
const TRACKS = {
  en: { code: "eng", title: "English" },
  fr: { code: "fre", title: "Français" },
};

// French says the same thing with a fifth more characters. Read at the same
// pace it runs late where the cues follow each other with no room, so it is
// read a bit faster. The build says how late each cue still is, and 1.2 is as
// fast as the API goes.
const SPEED = { fr: 1.1 };

const ELEVEN_SETTINGS = {
  stability: 0.7,
  similarity_boost: 0.75,
  style: 0,
  speed: 1,
  use_speaker_boost: true,
};

// How much of the surrounding text goes with a cue, so the voice knows where
// it is in the talk. It is not read out, only the cue itself is.
const CONTEXT_CHARS = 400;

// Silence kept at the head and the tail of a cue, and silence inserted when a
// cue has to be pushed.
const KEEP_HEAD = 0.04;
const KEEP_TAIL = 0.1;
const MIN_GAP = 0.02;
// Anything below this counts as silence.
const SILENCE_DB = -42;
// Short fades, so a cut never clicks.
const FADE = 0.015;

function run(command, args, options = {}) {
  const done = spawnSync(command, args, { maxBuffer: 1 << 28, ...options });
  if (done.error) throw done.error;
  if (done.status !== 0)
    throw new Error(
      `${command} failed (${done.status})\n${
        done.stderr?.toString().slice(-2000) ?? ""
      }`,
    );
  return done;
}

// ---------------------------------------------------------------- subtitles

function parseTime(text) {
  const found = text.trim().match(/^(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)$/);
  if (!found) throw new Error(`bad timestamp: ${text}`);
  return (
    Number(found[1] ?? 0) * 3600 + Number(found[2]) * 60 + Number(found[3])
  );
}

function formatTime(seconds, hours = true) {
  const total = Math.max(0, seconds);
  const rest = (total % 60).toFixed(3).padStart(6, "0");
  const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  if (!hours) return `${minutes}:${rest}`;
  const big = String(Math.floor(total / 3600)).padStart(2, "0");
  return `${big}:${minutes}:${rest}`;
}

// The header block and the shape of the timestamps are kept as they are, so a
// rebuilt file only differs by its timings.
function readVtt(path) {
  const blocks = readFileSync(path, "utf8")
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/);
  const cues = [];
  let header = "WEBVTT";
  let hours = true;
  blocks.forEach((block, index) => {
    const lines = block.split("\n").filter((line) => line.trim());
    const at = lines.findIndex((line) => line.includes("-->"));
    if (at < 0) {
      if (index === 0) header = block.trim();
      return;
    }
    const [from, rest] = lines[at].split("-->");
    const [to, ...settings] = rest.trim().split(/\s+/);
    if (!cues.length) hours = from.trim().split(":").length > 2;
    cues.push({
      id: at > 0 ? lines[at - 1] : "",
      start: parseTime(from),
      end: parseTime(to),
      settings: settings.join(" "),
      text: lines
        .slice(at + 1)
        .join(" ")
        .trim(),
    });
  });
  return { header, hours, cues };
}

function writeVtt(path, { header, hours, cues }) {
  const blocks = cues.map((cue) => {
    const timing = `${formatTime(cue.start, hours)} --> ${formatTime(
      cue.end,
      hours,
    )}${cue.settings ? ` ${cue.settings}` : ""}`;
    return [cue.id, timing, cue.text].filter(Boolean).join("\n");
  });
  writeFileSync(path, `${[header, ...blocks].join("\n\n")}\n`);
}

// What the voice should say. The subtitles start a continuation with an
// ellipsis, which reads as a stumble at the start of a take.
const speech = (text) =>
  text
    .replace(/^(?:\.\.\.|…)\s*/, "")
    .replace(/\s+/g, " ")
    .trim();

// One take per cue, numbered like the cue so the build report points straight
// at the file.
function makeTakes(cues) {
  return cues
    .map((cue, index) => ({
      id: index + 1,
      cue: index,
      text: speech(cue.text),
    }))
    .filter((take) => take.text);
}

// ------------------------------------------------------------- elevenlabs

function requestFor(takes, position, lang) {
  const take = takes[position];
  const before = takes
    .slice(0, position)
    .map((other) => other.text)
    .join(" ");
  const after = takes
    .slice(position + 1)
    .map((other) => other.text)
    .join(" ");
  const request = {
    text: take.text,
    model_id: ELEVEN_MODEL,
    voice_settings: {
      ...ELEVEN_SETTINGS,
      speed: SPEED[lang] ?? ELEVEN_SETTINGS.speed,
    },
    pronunciation_dictionary_locators: [
      { pronunciation_dictionary_id: DICTIONARY },
    ],
  };
  if (before) request.previous_text = before.slice(-CONTEXT_CHARS);
  if (after) request.next_text = after.slice(0, CONTEXT_CHARS);
  return request;
}

const keyOf = (request) =>
  createHash("sha256")
    .update(JSON.stringify({ request, voice: VOICE, format: ELEVEN_FORMAT }))
    .digest("hex")
    .slice(0, 16);

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function speak(request) {
  const key = process.env.ELEVENLABS_API_KEY;
  if (!key) throw new Error("ELEVENLABS_API_KEY is not set");
  const url =
    `https://api.elevenlabs.io/v1/text-to-speech/${VOICE}` +
    `?output_format=${ELEVEN_FORMAT}`;
  for (let attempt = 1; ; attempt++) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "xi-api-key": key,
        "content-type": "application/json",
        accept: "audio/mpeg",
      },
      body: JSON.stringify(request),
    });
    if (response.ok) return Buffer.from(await response.arrayBuffer());
    const detail = (await response.text()).slice(0, 400);
    const again = response.status === 429 || response.status >= 500;
    if (!again || attempt === 3)
      throw new Error(`ElevenLabs ${response.status}: ${detail}`);
    console.log(`  ${response.status}, retrying in ${attempt * 5}s`);
    await wait(attempt * 5000);
  }
}

// ------------------------------------------------------------------- audio

const duration = (path) =>
  Number(
    run("ffprobe", [
      "-v",
      "error",
      "-show_entries",
      "format=duration",
      "-of",
      "default=noprint_wrappers=1:nokey=1",
      path,
    ]).stdout.toString(),
  );

// One take, trimmed of the silence the voice leaves around it and faded at
// both ends, as raw samples.
function voiced(file) {
  const trim = [
    `silenceremove=start_periods=1:start_duration=0:start_threshold=${SILENCE_DB}dB:start_silence=${KEEP_HEAD}`,
    "areverse",
    `silenceremove=start_periods=1:start_duration=0:start_threshold=${SILENCE_DB}dB:start_silence=${KEEP_TAIL}`,
    `afade=t=in:st=0:d=${FADE}`,
    "areverse",
    `afade=t=in:st=0:d=${FADE}`,
  ].join(",");
  return run("ffmpeg", [
    "-hide_banner",
    "-loglevel",
    "error",
    "-i",
    file,
    "-af",
    trim,
    "-f",
    "s16le",
    "-ar",
    String(RATE),
    "-ac",
    "1",
    "-",
  ]).stdout;
}

// ------------------------------------------------------------------ steps

const OUT = join(HERE, "out");

const pad = (id) => String(id).padStart(3, "0");

const takeFile = (paths, id) => join(paths.tts, `${pad(id)}.${CONTAINER}`);

const dirs = (lang) => {
  const out = join(OUT, lang);
  const paths = { out, tts: join(out, "tts") };
  for (const path of Object.values(paths)) mkdirSync(path, { recursive: true });
  return paths;
};

function load(lang) {
  const vtt = readVtt(join(MEDIA, `${STEM}.${lang}.vtt`));
  const takes = makeTakes(vtt.cues);
  const paths = dirs(lang);
  writeFileSync(
    join(paths.out, "takes.json"),
    `${JSON.stringify(takes, null, 2)}\n`,
  );
  return { cues: vtt.cues, takes, paths };
}

function doPlan(lang) {
  const { cues, takes } = load(lang);
  for (const take of takes) {
    const cue = cues[take.cue];
    console.log(
      `${lang} ${pad(take.id)}  ${formatTime(cue.start)}  ` +
        `${String(take.text.length).padStart(3)} chars  ` +
        `${take.text.slice(0, 60)}`,
    );
  }
  const chars = takes.reduce((total, take) => total + take.text.length, 0);
  console.log(`\n${lang}: ${takes.length} cues, ${chars} chars\n`);
}

async function doTts(lang, redo, dryRun) {
  const { takes, paths } = load(lang);
  let spent = 0;
  for (let position = 0; position < takes.length; position++) {
    const take = takes[position];
    const file = takeFile(paths, take.id);
    const meta = join(paths.tts, `${pad(take.id)}.json`);
    const request = requestFor(takes, position, lang);
    const key = keyOf(request);
    const known =
      existsSync(file) &&
      existsSync(meta) &&
      JSON.parse(readFileSync(meta, "utf8")).key === key;
    if (known && !(redo === "all" || redo.has(take.id))) continue;
    spent += take.text.length;
    if (dryRun) {
      console.log(
        `${lang} ${pad(take.id)}  ${take.text.length} chars  would send`,
      );
      continue;
    }
    writeFileSync(file, await speak(request));
    writeFileSync(
      meta,
      `${JSON.stringify({ key, cue: take.cue, text: take.text })}\n`,
    );
    console.log(
      `${lang} ${pad(take.id)}  ${take.text.length} chars  ` +
        `${duration(file).toFixed(1)}s`,
    );
  }
  console.log(`${lang}: ${spent} characters${dryRun ? " to send" : " sent"}`);
}

// One voice track: every take dropped back at the time of its cue, with
// silence in between. Says where each cue ended up.
function assemble(lang) {
  const { cues, takes, paths } = load(lang);
  for (const take of takes) {
    const meta = join(paths.tts, `${pad(take.id)}.json`);
    if (!existsSync(takeFile(paths, take.id)) || !existsSync(meta))
      throw new Error(`${lang} cue ${take.id} not synthesized`);
    if (JSON.parse(readFileSync(meta, "utf8")).text !== take.text)
      throw new Error(`${lang} cue ${take.id} is stale, run tts again`);
  }

  const raw = join(paths.out, "voice.raw");
  const handle = openSync(raw, "w");
  const timing = [];
  let cursor = 0;
  try {
    for (const take of takes) {
      const cue = cues[take.cue];
      const pcm = voiced(takeFile(paths, take.id));
      const wanted = Math.round(cue.start * RATE);
      const earliest = cursor ? cursor + Math.round(MIN_GAP * RATE) : 0;
      const at = Math.max(wanted, earliest);
      writeSync(handle, Buffer.alloc((at - cursor) * 2));
      writeSync(handle, pcm);
      cursor = at + pcm.length / 2;
      timing.push({
        cue: take.cue,
        was: [cue.start, cue.end],
        now: [at / RATE, cursor / RATE],
        drift: at / RATE - cue.start,
      });
    }
    const total = Math.round(duration(VIDEO) * RATE);
    if (total > cursor) writeSync(handle, Buffer.alloc((total - cursor) * 2));
  } finally {
    closeSync(handle);
  }

  const wav = join(paths.out, "voice.wav");
  run("ffmpeg", [
    "-hide_banner",
    "-loglevel",
    "error",
    "-y",
    "-f",
    "s16le",
    "-ar",
    String(RATE),
    "-ac",
    "1",
    "-i",
    raw,
    "-c:a",
    "pcm_s16le",
    wav,
  ]);
  rmSync(raw);
  writeFileSync(
    join(paths.out, "timing.json"),
    `${JSON.stringify(timing, null, 2)}\n`,
  );
  return { lang, wav, timing, end: cursor / RATE };
}

// Each language keeps its own subtitles, since each one follows its own voice.
function retime(lang, timing) {
  const name = `${STEM}.${lang}.vtt`;
  const vtt = readVtt(join(MEDIA, name));
  const now = new Map(timing.map((entry) => [entry.cue, entry.now]));
  vtt.cues.forEach((cue, index) => {
    const found = now.get(index);
    if (found) [cue.start, cue.end] = found;
  });
  writeVtt(join(OUT, name), vtt);
}

function report(track) {
  const late = track.timing.filter((entry) => entry.drift > 0.05);
  for (const entry of late.slice(0, 10))
    console.log(
      `${track.lang} cue ${String(entry.cue + 1).padStart(3)}  ` +
        `${formatTime(entry.was[0])} -> ${formatTime(entry.now[0])}  ` +
        `+${entry.drift.toFixed(2)}s`,
    );
  if (late.length > 10)
    console.log(`${track.lang} … and ${late.length - 10} more`);
  const worst = late.reduce((most, entry) => Math.max(most, entry.drift), 0);
  console.log(
    `${track.lang}: ${late.length} cues pushed, worst by ${worst.toFixed(2)}s, ` +
      `voice ends at ${formatTime(track.end)}\n`,
  );
}

function doBuild(langs) {
  if (!VIDEO)
    throw new Error(`no ${STEM} video in ${MEDIA}, try git annex get`);
  const tracks = langs.map(assemble);
  for (const track of tracks) retime(track.lang, track.timing);

  // Matroska whatever the source container is, since FLAC in MP4 plays
  // almost nowhere.
  const video = join(OUT, `${STEM}.mkv`);
  const args = ["-hide_banner", "-loglevel", "error", "-y", "-i", VIDEO];
  for (const track of tracks) args.push("-i", track.wav);
  args.push("-map", "0:v:0");
  tracks.forEach((track, index) => args.push("-map", `${index + 1}:a:0`));
  args.push("-c:v", "copy", "-c:a", "flac");
  tracks.forEach((track, index) => {
    const { code, title } = TRACKS[track.lang];
    args.push(`-metadata:s:a:${index}`, `language=${code}`);
    args.push(`-metadata:s:a:${index}`, `title=${title}`);
    args.push(`-disposition:a:${index}`, index ? "0" : "default");
  });
  args.push("-shortest", video);
  run("ffmpeg", args);

  for (const track of tracks) report(track);
  console.log(`video ends at ${formatTime(duration(VIDEO))}\n${video}`);
}

// -------------------------------------------------------------------- main

function parseRedo(value) {
  if (!value) return new Set();
  if (value === "all") return "all";
  const wanted = new Set();
  for (const part of value.split(",")) {
    const range = part.match(/^(\d+)-(\d+)$/);
    if (range)
      for (let i = Number(range[1]); i <= Number(range[2]); i++) wanted.add(i);
    else wanted.add(Number(part));
  }
  return wanted;
}

const argv = process.argv.slice(2);
const option = (name, fallback) => {
  const at = argv.indexOf(`--${name}`);
  return at < 0 ? fallback : argv[at + 1];
};
// Anything that is not an option, nor the value of one, is the command.
const VALUED = ["--lang", "--redo"];
const words = argv.filter(
  (arg, index) =>
    !arg.startsWith("--") && !VALUED.includes(argv[index - 1] ?? ""),
);
const command = words[0] ?? "help";
const only = option("lang", "");
const langs = only ? [only] : LANGS;
const redo = parseRedo(option("redo", ""));
const dryRun = argv.includes("--dry-run");

switch (command) {
  case "plan":
    langs.forEach(doPlan);
    break;
  case "tts":
    for (const lang of langs) await doTts(lang, redo, dryRun);
    break;
  case "build":
    doBuild(langs);
    break;
  case "all":
    langs.forEach(doPlan);
    for (const lang of langs) await doTts(lang, redo, dryRun);
    doBuild(langs);
    break;
  default:
    console.log(
      readFileSync(fileURLToPath(import.meta.url), "utf8")
        .split("\n")
        .filter((line) => line.startsWith("//"))
        .map((line) => line.slice(3))
        .join("\n"),
    );
}
