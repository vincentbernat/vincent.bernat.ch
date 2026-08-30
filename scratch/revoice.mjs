#!/usr/bin/env node
//
// Add a French voice track to the spanning tree video. The English track is
// copied over untouched.
//
// The French subtitles give both the text and the timing. A sentence is read in
// one go, then dropped back at the time its first cue has in the subtitles.
// Starts stay where they are. Ends follow the voice, and a sentence that runs
// long pushes the next one.
//
// One sentence, one request. A cue is where the text breaks on screen, not
// where the reading breaks: the English was recorded a sentence at a time. Ask
// for half a sentence and the voice trails off into the words that follow,
// which is how it ends up saying the first word of the next cue as well. The
// text around the sentence is still sent, as context, so the tone carries over.
//
// A take also stops wherever the subtitles leave a gap, since that is where the
// reading stopped. Almost all of those sit after a colon, where the narrator
// waits on a BPDU or a diagram for a few seconds before going on.
//
// The cues of a sentence are timed from the character times the API returns
// with the audio, so a cue still starts on the right word. A take fetched
// before those were asked for has none, and its cues share the audio in
// proportion to how much of the text they hold instead.
//
// The French track is mixed the same way the English one was:
//
//   - the voice, levelled to -16 LUFS,
//   - the Algorhyme poem, which is Radia Perlman reading it herself. It is not
//     translated. Her reading goes back at its own place and holds it: the
//     voice that follows restarts where she stops, so the drift picked up
//     before her never carries past.
//   - a piano bed under the whole thing, on repeat, 24 LU below the voice and
//     half that under the poem.
//
// Usage:
//
//   node scratch/revoice.mjs plan            list the cues
//   node scratch/revoice.mjs tts             synthesize the missing cues
//   node scratch/revoice.mjs build           mix, mux, retime the subtitles
//   node scratch/revoice.mjs all             all of the above
//
// Options:
//
//   --redo 3,7-9     synthesize those cues again, even if cached
//   --redo all       synthesize everything again
//   --dry-run        with "tts": show what would be sent, send nothing
//
// Take audio is cached under scratch/out/tts, named after the first cue of the
// sentence, so a rerun only pays for what changed. When a word comes out wrong,
// fix it in the pronunciation dictionary, then redo the takes that contain it:
//
//   node scratch/revoice.mjs tts --redo 27
//   node scratch/revoice.mjs build
//
// The rebuilt video and the French subtitles land in scratch/out, the working
// files next to them. The subtitles keep their text and take the timings of
// the French voice, which is why they no longer share the timings of the
// English ones.
//
// The result stays an MP4, under the name tasks.py and the HLS playlist know.
// "fra" is the language code that gives "français" in the playlist, whether or
// not the name on the track is picked up.
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
const STEM = "2026-spanning-tree";
const VIDEO = join(MEDIA, `${STEM}.mp4`);

// The cloned voice and the dictionary that fixes the technical words. Alias
// rules work with any model. Phoneme rules only work with eleven_turbo_v2 and
// eleven_flash_v2, so set ELEVEN_MODEL when the dictionary uses them.
const VOICE = "m2MRSLlg6HZtNmBXNyFO"; // my pro voice
const DICTIONARY = "lnCqCHgcKIrhkj9F2M1r"; // the French dictionary
const ELEVEN_MODEL = process.env.ELEVEN_MODEL ?? "eleven_multilingual_v2";
const ELEVEN_FORMAT = process.env.ELEVEN_FORMAT ?? "mp3_44100_128";
// Cues are kept in the format they arrive in, and the voice is built at their
// own sample rate, so it is never resampled before the mix.
const CONTAINER = ELEVEN_FORMAT.split("_")[0];
if (CONTAINER !== "wav" && CONTAINER !== "mp3")
  throw new Error(`ELEVEN_FORMAT must be wav_* or mp3_*, not ${ELEVEN_FORMAT}`);
const RATE = Number(ELEVEN_FORMAT.split("_")[1]);

// What each track is called. Matroska would want "fre" for the language, MP4
// wants "fra". A name set as "title" lands in the QuickTime atom MP4 keeps for
// it, which ffprobe reads back as "name".
const ENGLISH = { language: "eng", title: "English" };
const FRENCH = { language: "fra", title: "français" };

// French says the same thing with a fifth more characters. Read at the same
// pace it runs late where the cues follow each other with no room, so it is
// read a bit faster. The build says how late each cue still is, and 1.2 is as
// fast as the API goes.
const SPEED = 1.1;

const ELEVEN_SETTINGS = {
  stability: 0.7,
  similarity_boost: 0.75,
  style: 0,
  speed: SPEED,
  use_speaker_boost: true,
};

// How much of the surrounding text goes with a cue, so the voice knows where
// it is in the talk. It is not read out, only the cue itself is.
const CONTEXT_CHARS = 400;

// The dictionaries a take may have been read under, newest first. Swapping one
// for another leaves the key alone, so only the takes named with --redo are
// read again.
const DICTIONARIES = [DICTIONARY, "JJkVw7kU7FwOZTDi5Feu"];

// The first and the last cue of the poem, as numbered in the subtitles. They
// are never sent for reading.
const POEM = [37, 48];
const POEM_AUDIO = join(HERE, "assets/radia-algorhyme.ogg");

// The bed under the whole video, on repeat. Same piece and same levels as the
// English track, so the two sound alike.
const MUSIC = join(HERE, "assets/aaron-dunn-sonatina-no-2-in-g-major.mp3");
const MUSIC_LUFS = Number(process.env.MUSIC_LUFS ?? -40);
const MUSIC_FADE = 4;
// Half the level under the poem, reached over this many seconds.
const MUSIC_DUCK = 0.5;
const MUSIC_DUCK_FADE = 2;

// Where the voice sits, in LUFS, the true peak ceiling and the lift given to
// the finished mix, both in dB.
const VOICE_LUFS = -16;
const PEAK = -2.0;
const LIFT = Number(process.env.AUDIO_GAIN ?? 2.5);

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
      // Line breaks are kept: they are how the cue is laid out on screen.
      text: lines
        .slice(at + 1)
        .join("\n")
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

const inPoem = (number) => number >= POEM[0] && number <= POEM[1];

// A trailing emoji does not end a sentence, and neither does the guillemet of a
// quoted word. Only the mark counts.
const ends = (text) =>
  /[.!?]$/.test(text.replace(/[\p{Extended_Pictographic}\uFE0F\s]+$/u, ""));

// A gap between two cues is where the reading stopped. Cues either run on with
// no gap at all or leave close to half a second, so anything in between never
// comes up. Most of these sit after a colon, where the narrator waits for the
// viewer to read what is on screen.
const SPLIT_GAP = 0.25;

// One take per sentence, numbered after its first cue so the build report
// points straight at the file. A take also stops where the reading stopped,
// which is not always the end of a sentence: a colon that puts something on
// screen is held for several seconds. The poem breaks a take in two as well,
// since nothing is read across her.
function makeTakes(cues) {
  const takes = [];
  let current = null;
  cues.forEach((cue, index) => {
    if (inPoem(index + 1)) {
      current = null;
      return;
    }
    const text = speech(cue.text);
    if (!text) return;
    if (!current) {
      current = { id: index + 1, cues: [], text: "" };
      takes.push(current);
    }
    current.cues.push(index);
    current.text = current.text ? `${current.text} ${text}` : text;
    const next = cues[index + 1];
    const paused = !next || next.start - cue.end >= SPLIT_GAP;
    if (ends(text) || paused) current = null;
  });
  return takes;
}

// ------------------------------------------------------------- elevenlabs

function requestFor(takes, position) {
  const take = takes[position];
  // Nothing is taken from the other side of the poem: what comes before and
  // after her is her, not the French voice.
  const early = take.cues[0] < POEM[0] - 1;
  const same = (other) => other.cues[0] < POEM[0] - 1 === early;
  const before = takes
    .slice(0, position)
    .filter(same)
    .map((other) => other.text)
    .join(" ");
  const after = takes
    .slice(position + 1)
    .filter(same)
    .map((other) => other.text)
    .join(" ");
  const request = {
    text: take.text,
    model_id: ELEVEN_MODEL,
    voice_settings: ELEVEN_SETTINGS,
    pronunciation_dictionary_locators: [
      { pronunciation_dictionary_id: DICTIONARY },
    ],
  };
  if (before) request.previous_text = before.slice(-CONTEXT_CHARS);
  if (after) request.next_text = after.slice(0, CONTEXT_CHARS);
  return request;
}

const digest = (request) =>
  createHash("sha256")
    .update(JSON.stringify({ request, voice: VOICE, format: ELEVEN_FORMAT }))
    .digest("hex")
    .slice(0, 16);

// Every key the take could be filed under: one with no dictionary at all, and
// one per dictionary it may have been read with. The first is what a new take
// gets, so the pile stops growing. A word whose pronunciation changed is read
// again with --redo, not by throwing the whole cache away.
const keysOf = (request) => {
  const bare = { ...request };
  delete bare.pronunciation_dictionary_locators;
  return [
    digest(bare),
    ...DICTIONARIES.map((id) =>
      digest({
        ...request,
        pronunciation_dictionary_locators: [
          { pronunciation_dictionary_id: id },
        ],
      }),
    ),
  ];
};

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// The audio comes back base64 in JSON, with the time of every character of the
// text next to it. "alignment" is against the text as it was sent, which is
// what the cue boundaries are counted in. "normalized_alignment" is against
// the text the model rewrote for itself, where a number became words, so it
// cannot be indexed the same way.
async function speak(request) {
  const key = process.env.ELEVENLABS_API_KEY;
  if (!key) throw new Error("ELEVENLABS_API_KEY is not set");
  const url =
    `https://api.elevenlabs.io/v1/text-to-speech/${VOICE}/with-timestamps` +
    `?output_format=${ELEVEN_FORMAT}`;
  for (let attempt = 1; ; attempt++) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "xi-api-key": key,
        "content-type": "application/json",
        accept: "application/json",
      },
      body: JSON.stringify(request),
    });
    if (response.ok) {
      const body = await response.json();
      return {
        audio: Buffer.from(body.audio_base64, "base64"),
        alignment: body.alignment,
      };
    }
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

// A fixed gain keeps the music as played. loudnorm would flatten it, which is
// the opposite of what a bed needs.
function musicGain(file) {
  const text = run("ffmpeg", [
    "-hide_banner",
    "-nostats",
    "-i",
    file,
    "-af",
    "ebur128",
    "-f",
    "null",
    "-",
  ]).stderr.toString();
  const found = text.match(/Integrated loudness:\s*\n\s*I:\s+(-?[\d.]+)/);
  if (!found) throw new Error(`cannot measure the loudness of ${file}`);
  return Number((MUSIC_LUFS - Number(found[1])).toFixed(2));
}

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
const TTS = join(OUT, "tts");

const pad = (id) => String(id).padStart(3, "0");

const takeFile = (id) => join(TTS, `${pad(id)}.${CONTAINER}`);

function load() {
  mkdirSync(TTS, { recursive: true });
  const vtt = readVtt(join(MEDIA, `${STEM}.fr.vtt`));
  const takes = makeTakes(vtt.cues);
  writeFileSync(join(OUT, "takes.json"), `${JSON.stringify(takes, null, 2)}\n`);
  // Her reading has to land on the cues that carry its translation. A mismatch
  // means the poem moved in the subtitles and POEM is out of date.
  const poem = {
    at: vtt.cues[POEM[0] - 1].start,
    seconds: duration(POEM_AUDIO),
  };
  const span = vtt.cues[POEM[1] - 1].end - poem.at;
  if (Math.abs(span - poem.seconds) > 0.5)
    console.log(
      `warning: cues ${POEM[0]}-${POEM[1]} last ${span.toFixed(2)}s, ` +
        `${POEM_AUDIO} lasts ${poem.seconds.toFixed(2)}s`,
    );
  return { cues: vtt.cues, takes, poem };
}

function doPlan() {
  const { cues, takes, poem } = load();
  for (const take of takes) {
    const first = cues[take.cues[0]];
    const span =
      take.cues.length > 1
        ? `${take.id}-${take.cues[take.cues.length - 1] + 1}`
        : String(take.id);
    console.log(
      `${pad(take.id)}  ${formatTime(first.start)}  ` +
        `${String(take.text.length).padStart(3)} chars  ` +
        `cues ${span.padEnd(7)} ${take.text.slice(0, 52)}`,
    );
  }
  const chars = takes.reduce((total, take) => total + take.text.length, 0);
  const spoken = takes.reduce((total, take) => total + take.cues.length, 0);
  console.log(`\n${takes.length} takes over ${spoken} cues, ${chars} chars`);
  console.log(
    `poem read at ${formatTime(poem.at)} for ${poem.seconds.toFixed(2)}s, ` +
      `cues ${POEM[0]} to ${POEM[1]}\n`,
  );
}

async function doTts(redo, dryRun) {
  const { takes } = load();
  let spent = 0;
  for (let position = 0; position < takes.length; position++) {
    const take = takes[position];
    const file = takeFile(take.id);
    const path = join(TTS, `${pad(take.id)}.json`);
    const request = requestFor(takes, position);
    const keys = keysOf(request);
    const meta = existsSync(path)
      ? JSON.parse(readFileSync(path, "utf8"))
      : null;
    const known = existsSync(file) && meta !== null && keys.includes(meta.key);
    if (known && !(redo === "all" || redo.has(take.id))) continue;
    spent += take.text.length;
    if (dryRun) {
      console.log(`${pad(take.id)}  ${take.text.length} chars  would send`);
      continue;
    }
    const { audio, alignment } = await speak(request);
    writeFileSync(file, audio);
    writeFileSync(
      path,
      `${JSON.stringify({
        key: keys[0],
        cues: take.cues,
        text: take.text,
        alignment,
      })}\n`,
    );
    console.log(
      `${pad(take.id)}  ${take.text.length} chars  ${duration(file).toFixed(1)}s`,
    );
  }
  console.log(`${spent} characters${dryRun ? " to send" : " sent"}`);
}

// Where each cue of a take ends, in samples. The character times that came back
// with the audio put the cut on the right word. Trimming moved the first word
// to KEEP_HEAD, so every time shifts along with it. Without them the cues share
// the take in proportion to how much of the text they hold.
function boundaries(take, meta, cues, at, end) {
  const shares = take.cues.map((index) => speech(cues[index].text).length);
  const whole = shares.reduce((sum, share) => sum + share, 0);
  const align = meta.alignment;
  const times = align?.character_end_times_seconds;
  // One entry per character the API saw, which is not one per position in the
  // text: an emoji counts once there and twice here. Walking it once lines the
  // two up, and a text that does not come back whole is not used at all.
  const endOf = new Map();
  const timed = Boolean(times) && align.characters.join("") === take.text;
  if (timed) {
    let used = 0;
    align.characters.forEach((character, position) => {
      used += character.length;
      endOf.set(used - 1, times[position]);
    });
  }
  const shift = timed ? KEEP_HEAD - align.character_start_times_seconds[0] : 0;
  const marks = [at];
  let sum = 0;
  let missed = false;
  shares.slice(0, -1).forEach((share, position) => {
    sum += share;
    // The cues are joined by one space, so the last character of cue n sits
    // n places further along than its own text would say.
    const time = endOf.get(sum + position - 1);
    const mark =
      time === undefined
        ? at + Math.round(((end - at) * sum) / whole)
        : at + Math.round((time + shift) * RATE);
    if (time === undefined) missed = true;
    marks.push(Math.min(Math.max(mark, marks[marks.length - 1]), end));
  });
  marks.push(end);
  return { marks, timed: timed && !missed };
}

// The voice track: every take dropped back at the time of its cue, with
// silence in between and nothing where the poem goes. Says where each cue
// ended up.
function assemble(cues, takes, poem, length) {
  const metas = new Map();
  for (const take of takes) {
    const path = join(TTS, `${pad(take.id)}.json`);
    if (!existsSync(takeFile(take.id)) || !existsSync(path))
      throw new Error(`take ${take.id} not synthesized`);
    const meta = JSON.parse(readFileSync(path, "utf8"));
    if (meta.text !== take.text)
      throw new Error(`take ${take.id} is stale, run tts again`);
    metas.set(take.id, meta);
  }

  const poemEnd = poem.at + poem.seconds;
  const raw = join(OUT, "voice.raw");
  const handle = openSync(raw, "w");
  const timing = [];
  let over = 0;
  let guessed = 0;
  let cursor = 0;
  try {
    for (const take of takes) {
      const first = cues[take.cues[0]];
      const pcm = voiced(takeFile(take.id));
      const wanted = Math.round(first.start * RATE);
      let earliest = cursor ? cursor + Math.round(MIN_GAP * RATE) : 0;
      // She holds her place, so what follows her waits for her to finish.
      if (take.cues[0] > POEM[1] - 1)
        earliest = Math.max(earliest, Math.round(poemEnd * RATE));
      const at = Math.max(wanted, earliest);
      writeSync(handle, Buffer.alloc((at - cursor) * 2));
      writeSync(handle, pcm);
      cursor = at + pcm.length / 2;
      if (take.cues[0] < POEM[0] - 1 && cursor > poem.at * RATE) over++;
      const cut = boundaries(take, metas.get(take.id), cues, at, cursor);
      if (take.cues.length > 1 && !cut.timed) guessed++;
      take.cues.forEach((index, position) => {
        timing.push({
          cue: index,
          was: [cues[index].start, cues[index].end],
          now: [cut.marks[position] / RATE, cut.marks[position + 1] / RATE],
          drift: cut.marks[position] / RATE - cues[index].start,
        });
      });
    }
    const total = Math.round(length * RATE);
    if (total > cursor) writeSync(handle, Buffer.alloc((total - cursor) * 2));
  } finally {
    closeSync(handle);
  }

  // The track is the length of the video, whatever the voice does. A voice
  // that runs past the end is cut, and the report says by how much.
  const wav = join(OUT, "voice.wav");
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
    "-t",
    String(length),
    "-c:a",
    "pcm_s16le",
    wav,
  ]);
  rmSync(raw);
  writeFileSync(
    join(OUT, "timing.json"),
    `${JSON.stringify(timing, null, 2)}\n`,
  );
  return { wav, timing, over, guessed, end: cursor / RATE };
}

// The English track is copied over, the French one is the voice, the poem and
// the bed mixed together. amix would rescale every side without normalize=0.
function mux(track, poem, length) {
  const poemEnd = poem.at + poem.seconds;
  const ramp = MUSIC_DUCK_FADE;
  // The ramps sit outside the poem, so the bed is already down when she starts
  // and only comes back up once she has finished.
  const duck =
    `volume='1-${1 - MUSIC_DUCK}*clip(min((t-${Math.max(0, poem.at - ramp).toFixed(3)})/${ramp},` +
    `(${(poemEnd + ramp).toFixed(3)}-t)/${ramp}),0,1)':eval=frame,`;
  // loudnorm runs at 192 kHz, so everything is brought back to the rate of the
  // English track before the mix.
  const shape =
    "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo";
  const level = `loudnorm=I=${VOICE_LUFS}:TP=${PEAK}:LRA=11`;
  const graph =
    `[1:a]${level},${shape}[v];` +
    `[2:a]${level},${shape},adelay=${Math.round(poem.at * 1000)}:all=1[p];` +
    `[3:a]volume=${musicGain(MUSIC)}dB,${duck}` +
    `afade=t=in:st=0:d=${MUSIC_FADE},` +
    `afade=t=out:st=${Math.max(0, length - MUSIC_FADE).toFixed(3)}:d=${MUSIC_FADE},` +
    `${shape}[m];` +
    `[v][p][m]amix=inputs=3:duration=first:normalize=0,volume=${LIFT}dB[a]`;

  const video = join(OUT, `${STEM}.mp4`);
  run("ffmpeg", [
    "-hide_banner",
    "-loglevel",
    "error",
    "-y",
    "-i",
    VIDEO,
    "-i",
    track.wav,
    "-i",
    POEM_AUDIO,
    "-stream_loop",
    "-1",
    "-i",
    MUSIC,
    "-filter_complex",
    graph,
    "-map",
    "0:v:0",
    "-map",
    "0:a:0",
    "-map",
    "[a]",
    "-map_chapters",
    "0",
    "-c:v",
    "copy",
    "-c:a:0",
    "copy",
    "-c:a:1",
    "aac",
    "-b:a:1",
    "192k",
    "-metadata:s:a:0",
    `language=${ENGLISH.language}`,
    "-metadata:s:a:0",
    `title=${ENGLISH.title}`,
    "-metadata:s:a:1",
    `language=${FRENCH.language}`,
    "-metadata:s:a:1",
    `title=${FRENCH.title}`,
    "-disposition:a:0",
    "default",
    "-disposition:a:1",
    "0",
    video,
  ]);
  return video;
}

// The French subtitles follow the French voice, so they no longer share the
// timings of the English ones. The poem keeps its own: it did not move.
function retime(timing) {
  const name = `${STEM}.fr.vtt`;
  const vtt = readVtt(join(MEDIA, name));
  const now = new Map(timing.map((entry) => [entry.cue, entry.now]));
  vtt.cues.forEach((cue, index) => {
    const found = now.get(index);
    if (found) [cue.start, cue.end] = found;
  });
  // A sentence that runs long stops at the next one rather than sitting on top
  // of it. Only the poem can be reached this way, and the report says so.
  vtt.cues.forEach((cue, index) => {
    const next = vtt.cues[index + 1];
    if (next && cue.end > next.start) cue.end = next.start;
  });
  writeVtt(join(OUT, name), vtt);
}

function report(track, poem, length) {
  const late = track.timing.filter((entry) => entry.drift > 0.05);
  for (const entry of late.slice(0, 10))
    console.log(
      `cue ${String(entry.cue + 1).padStart(3)}  ` +
        `${formatTime(entry.was[0])} -> ${formatTime(entry.now[0])}  ` +
        `+${entry.drift.toFixed(2)}s`,
    );
  if (late.length > 10) console.log(`… and ${late.length - 10} more`);
  const worst = late.reduce((most, entry) => Math.max(most, entry.drift), 0);
  console.log(
    `${late.length} cues pushed, worst by ${worst.toFixed(2)}s, ` +
      `voice ends at ${formatTime(track.end)}`,
  );
  if (track.over)
    console.log(
      `${track.over} sentence(s) run into the poem at ${formatTime(poem.at)}: ` +
        `raise SPEED or shorten them`,
    );
  if (track.guessed)
    console.log(
      `${track.guessed} sentence(s) came without character times, ` +
        `their cues share the audio by length`,
    );
  if (track.end > length)
    console.log(
      `voice cut at the end of the video, ` +
        `${(track.end - length).toFixed(2)}s of it lost`,
    );
  console.log(
    `music at ${MUSIC_LUFS} LUFS, half that under the poem, ` +
      `mix lifted by ${LIFT} dB`,
  );
}

function doBuild() {
  if (!existsSync(VIDEO))
    throw new Error(`no ${STEM}.mp4 in ${MEDIA}, try git annex get`);
  for (const asset of [POEM_AUDIO, MUSIC])
    if (!existsSync(asset)) throw new Error(`missing ${asset}`);
  const { cues, takes, poem } = load();
  const length = duration(VIDEO);
  const track = assemble(cues, takes, poem, length);
  retime(track.timing);
  const video = mux(track, poem, length);
  report(track, poem, length);
  console.log(`video ends at ${formatTime(length)}\n${video}`);
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
const VALUED = ["--redo"];
const words = argv.filter(
  (arg, index) =>
    !arg.startsWith("--") && !VALUED.includes(argv[index - 1] ?? ""),
);
const command = words[0] ?? "help";
const redo = parseRedo(option("redo", ""));
const dryRun = argv.includes("--dry-run");

switch (command) {
  case "plan":
    doPlan();
    break;
  case "tts":
    await doTts(redo, dryRun);
    break;
  case "build":
    doBuild();
    break;
  case "all":
    doPlan();
    await doTts(redo, dryRun);
    doBuild();
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
