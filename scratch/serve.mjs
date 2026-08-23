// Static server for the video stage. It serves scratch/ plus the article's own
// CSS and JS, so the widgets on the stage look and behave exactly like the ones
// on the site.
//
//   node scratch/serve.mjs [port]

import { createServer } from "node:http";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";
import { tmpdir } from "node:os";
import {
  readFile,
  writeFile,
  stat,
  mkdir,
  readdir,
  unlink,
  copyFile,
  open,
} from "node:fs/promises";
import { dirname, extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// Paths are anchored to this file, not to the working directory, so the scripts
// run the same from scratch/ or anywhere else.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

// A wrapper can pass its own flags through to the script, so take the argument
// only when it really is a port. Number("--share-net") is NaN, and listening on
// NaN fails with a message that points nowhere near the cause.
const arg = process.argv[2];
const PORT = arg === undefined ? 8081 : /^\d+$/.test(arg) ? Number(arg) : 8081;
if (arg !== undefined && PORT !== Number(arg))
  console.warn(`ignoring "${arg}", which is not a port; using ${PORT}`);
const ROOT = resolve(REPO);

// URL prefix -> directory on disk.
const MOUNTS = [
  ["/media/", "content/media"],
  ["/site-css/", "deploy/media/css"],
  ["/", "scratch"],
];

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ogg": "audio/ogg",
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
  ".m4a": "audio/mp4",
  ".woff2": "font/woff2",
};

// The widget keeps everything private except this map and the mount entry
// point. Handing them to the page is enough for the recorder: it drives the
// cues by clicking a control link, and reads widget state to tell when an
// animation has finished.
const EPILOGUE = `
window.__mstp = { widgets, mountAll };
window.dispatchEvent(new Event("mstp:ready"));
`;

function resolvePath(urlPath) {
  const clean = normalize(decodeURIComponent(urlPath.split("?")[0]));
  if (clean.includes("..")) return null;
  for (const [prefix, dir] of MOUNTS) {
    if (!clean.startsWith(prefix)) continue;
    const rest = clean.slice(prefix.length) || "index.html";
    return {
      file: resolve(join(ROOT, dir, rest)),
      dir: resolve(join(ROOT, dir)),
    };
  }
  return null;
}

const AUDIO_DIR = join(HERE, "audio");
const TAKES_DIR = join(AUDIO_DIR, "takes");
const SELECTED = join(TAKES_DIR, "selected.json");
const SCRIPTS = join(TAKES_DIR, "scripts.json");
const COVERAGE = join(TAKES_DIR, "coverage.json");
const ORIGINS = join(TAKES_DIR, "origins.json");
const VOICE_SETTINGS = join(TAKES_DIR, "voice.json");
const BITRATE = process.env.AUDIO_BITRATE ?? "128k";

// Every take starts the same way, whoever said it: whatever silence it opens
// with is cut, then a fixed lead-in is put back. The cue fires with the first
// frame of video, so a take opening on a second of room tone would animate in
// silence while the next one speaks at once.
const LEAD = Number(process.env.AUDIO_LEAD ?? 0.15);
const LEAD_FILTER =
  "silenceremove=start_periods=1:start_duration=0:start_threshold=-40dB:detection=peak," +
  `adelay=${Math.round(LEAD * 1000)}:all=1,` +
  // The trim leaves the timestamps where they were and the delay carries them
  // along, so rebuild them from the sample count. Without this the muxer sees
  // them run backwards. The delay inserts real samples, so nothing is lost.
  "asetpts=N/SR/TB";

// The voices a take can be made with. The short label is what the takes list
// shows, where a full name would not fit.
const ELEVEN_KEY = process.env.ELEVENLABS_API_KEY ?? "";
const ELEVEN_VOICES = [
  {
    id: "m2MRSLlg6HZtNmBXNyFO",
    name: "Vincent Bernat (Professional Voice Clone)",
    label: "Vince(P)",
  },
  {
    id: "bLymryx2wj6AUhaEijF9",
    name: "Vincent Bernat (Instant Voice Clone)",
    label: "Vince(I)",
  },
  { id: "kiw9hkUW1gcPQwsQSs4e", name: "Cyril", label: "Cyril" },
];
const ELEVEN_VOICE =
  ELEVEN_VOICES.find(
    (v) =>
      v.id === process.env.ELEVENLABS_VOICE ||
      v.name === process.env.ELEVENLABS_VOICE,
  ) ?? ELEVEN_VOICES[0];
const ELEVEN_MODEL = process.env.ELEVENLABS_MODEL ?? "eleven_multilingual_v2";
// Made and edited in the ElevenLabs interface, the same way the voices are.
const ELEVEN_DICTIONARY =
  process.env.ELEVENLABS_DICTIONARY ?? "JJkVw7kU7FwOZTDi5Feu";
const ELEVEN_SETTINGS = {
  stability: 0.7,
  similarity_boost: 0.75,
  style: 0,
  speed: 1,
  use_speaker_boost: true,
};

// What the sliders may ask for. ElevenLabs rejects a speed outside this range,
// and the rest are fractions.
const ELEVEN_RANGE = {
  stability: [0, 1],
  similarity_boost: [0, 1],
  style: [0, 1],
  speed: [0.7, 1.2],
};
const VOICE =
  process.env.PIPER_VOICE ?? join(HERE, "models/en_US-lessac-medium.onnx");
const run = promisify(execFile);

// How long each take is, keyed by file and modification time. Measuring one
// means spawning an ffprobe, and there are a couple of hundred takes, so the
// answers are kept on disk: without that every restart pays for all of them
// again before the recorder can draw anything.
const LENGTHS = join(HERE, "out/take-lengths.json");
const lengths = new Map(
  (() => {
    try {
      return Object.entries(JSON.parse(readFileSync(LENGTHS, "utf8")));
    } catch {
      return [];
    }
  })(),
);
let lengthsDirty = false;

async function saveLengths() {
  if (!lengthsDirty) return;
  lengthsDirty = false;
  await writeFile(LENGTHS, JSON.stringify(Object.fromEntries(lengths)));
}

// Enough at once to keep the machine busy, few enough not to fork two hundred
// processes at the same moment.
async function inParallel(items, limit, work) {
  const out = new Array(items.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, async () => {
      for (let i = next++; i < items.length; i = next++)
        out[i] = await work(items[i]);
    }),
  );
  return out;
}

const isAudio = (file) => /\.(mp3|wav|m4a|flac|ogg|opus)$/.test(file);
const slugOf = (file) => file.replace(/^\d+-/, "").replace(/\.[^.]+$/, "");
const takeOf = (file) => Number(file.match(/\.take(\d+)\./)?.[1] ?? 0);
const takeSlug = (file) => file.replace(/\.take\d+\.[^.]+$/, "");

async function readSelected() {
  try {
    return JSON.parse(await readFile(SELECTED, "utf8"));
  } catch {
    return {};
  }
}

async function readScripts() {
  try {
    return JSON.parse(await readFile(SCRIPTS, "utf8"));
  } catch {
    return {};
  }
}

async function readCoverage() {
  try {
    return JSON.parse(await readFile(COVERAGE, "utf8"));
  } catch {
    return {};
  }
}

async function readOrigins() {
  try {
    return JSON.parse(await readFile(ORIGINS, "utf8"));
  } catch {
    return {};
  }
}

// The sliders are global, so they live in one file rather than per segment.
async function readVoiceConfig() {
  let saved = {};
  try {
    saved = JSON.parse(await readFile(VOICE_SETTINGS, "utf8"));
  } catch {}
  const settings = { ...ELEVEN_SETTINGS };
  for (const [name, [low, high]] of Object.entries(ELEVEN_RANGE)) {
    const value = Number(saved[name]);
    if (Number.isFinite(value))
      settings[name] = Math.min(high, Math.max(low, value));
  }
  // The settings go to ElevenLabs as they are, so the voice is kept apart from
  // them rather than sent along as a field it does not know.
  const voice = ELEVEN_VOICES.find((v) => v.id === saved.voice) ?? ELEVEN_VOICE;
  return { settings, voice };
}

// Whisper runs synchronously, so measuring a take in this process would stop
// the server answering anything else for several seconds — long enough that a
// word lookup made just after recording appears to hang. It runs as a child
// process instead, one at a time, and the figure is picked up from the cache on
// the next status.
let measuring = Promise.resolve();

function measureTake(slug, take) {
  const key = `${slug}.take${take}`;
  measuring = measuring.then(
    () =>
      new Promise((resolve) => {
        const child = spawn(
          process.execPath,
          [join(HERE, "coverage.mjs"), "--take", key],
          { stdio: ["ignore", "ignore", "inherit"] },
        );
        child.on("error", (err) => {
          console.warn(`${key}: cannot measure (${err.message})`);
          resolve();
        });
        child.on("close", () => resolve());
      }),
  );
  return measuring;
}

// segments.json is a few hundred kilobytes and a status call needs one line
// from it per take. Read it once and hold it until it changes on disk.
let segmentCache = { at: 0, bySlug: new Map() };
async function segments() {
  const file = join(HERE, "out/segments.json");
  const info = await stat(file);
  if (info.mtimeMs !== segmentCache.at) {
    const data = JSON.parse(await readFile(file, "utf8"));
    segmentCache = {
      at: info.mtimeMs,
      bySlug: new Map(data.segments.map((s) => [s.slug, s])),
    };
  }
  return segmentCache.bySlug;
}

async function segmentText(slug) {
  return (await segments()).get(slug)?.text ?? "";
}

const textStamp = (text) =>
  createHash("sha256").update(text).digest("hex").slice(0, 12);

async function saveSelected(selected) {
  await writeFile(SELECTED, JSON.stringify(selected, null, 2));
}

async function takeFiles(slug) {
  return (await readdir(TAKES_DIR))
    .filter((f) => isAudio(f) && takeSlug(f) === slug)
    .map(takeOf)
    .sort((a, b) => b - a);
}

function feed(command, args, input) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["pipe", "ignore", "pipe"] });
    let complaint = "";
    child.stderr.on("data", (chunk) => (complaint += chunk));
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0
        ? resolve()
        : reject(new Error(complaint.trim() || `${command} exited ${code}`)),
    );
    child.stdin.end(input);
  });
}

// The reference reading of a line, made when it is asked for. piper takes about
// a second, which is quicker than deciding whether a cached clip still matches
// the wording it was made from.
async function speak(text) {
  if (!existsSync(VOICE)) {
    const err = new Error(`no piper voice at ${VOICE}`);
    err.code = "ENOVOICE";
    throw err;
  }
  const stem = join(tmpdir(), `say-${process.pid}-${Math.abs(hashOf(text))}`);
  try {
    await feed("piper", ["-m", VOICE, "-f", `${stem}.wav`], text);
    await run("ffmpeg", [
      "-hide_banner",
      "-loglevel",
      "error",
      "-y",
      "-i",
      `${stem}.wav`,
      "-codec:a",
      "libmp3lame",
      "-b:a",
      BITRATE,
      "-ac",
      "1",
      `${stem}.mp3`,
    ]);
    return await readFile(`${stem}.mp3`);
  } finally {
    await unlink(`${stem}.wav`).catch(() => {});
    await unlink(`${stem}.mp3`).catch(() => {});
  }
}

function hashOf(text) {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0;
  return h;
}

async function reference(slug) {
  const data = JSON.parse(
    await readFile(join(HERE, "out/segments.json"), "utf8"),
  );
  const segment = data.segments.find((s) => s.slug === slug);
  if (!segment?.text) throw new Error(`no text for ${slug}`);
  return speak(segment.text);
}

async function takePath(slug, take) {
  const match = (await readdir(TAKES_DIR)).find(
    (f) => isAudio(f) && takeSlug(f) === slug && takeOf(f) === take,
  );
  return join(TAKES_DIR, match ?? `${slug}.take${take}.mp3`);
}

async function clearActive(slug) {
  for (const file of await readdir(AUDIO_DIR))
    if (isAudio(file) && slugOf(file) === slug)
      await unlink(join(AUDIO_DIR, file));
}

async function seconds(file) {
  const info = await stat(file);
  const key = `${file}:${info.mtimeMs}`;
  if (lengths.has(key)) return lengths.get(key);
  try {
    const { stdout } = await run("ffprobe", [
      "-v",
      "error",
      "-show_entries",
      "format=duration",
      "-of",
      "default=noprint_wrappers=1:nokey=1",
      file,
    ]);
    const value = Number(stdout.trim()) || null;
    lengths.set(key, value);
    lengthsDirty = true;
    return value;
  } catch {
    return null;
  }
}

async function describe(file) {
  const info = await stat(join(TAKES_DIR, file));
  return {
    file,
    take: takeOf(file),
    bytes: info.size,
    seconds: await seconds(join(TAKES_DIR, file)),
    at: info.mtimeMs,
  };
}

async function audioStatus() {
  await mkdir(TAKES_DIR, { recursive: true });
  const selected = await readSelected();
  const bySlug = {};

  const files = (await readdir(TAKES_DIR)).filter(isAudio);
  for (const take of await inParallel(files, 16, describe))
    (bySlug[takeSlug(take.file)] ??= { takes: [] }).takes.push(take);

  let adopted = false;
  for (const file of await readdir(AUDIO_DIR)) {
    if (!isAudio(file)) continue;
    const slug = slugOf(file);
    const entry = (bySlug[slug] ??= { takes: [] });
    entry.active = file;
    if (!entry.takes.length) {
      const name = `${slug}.take1${extname(file)}`;
      await copyFile(join(AUDIO_DIR, file), join(TAKES_DIR, name));
      entry.takes.push(await describe(name));
      selected[slug] = 1;
      adopted = true;
    }
  }
  if (adopted) await saveSelected(selected);

  // A take is matched to its segment by slug, and a slug only comes from the
  // opening of a paragraph. Editing the end of one would otherwise leave a
  // recording of the old wording paired with the new script, so what was on
  // screen when each take was made is stamped alongside it.
  const scripts = await readScripts();
  const reached = await readCoverage();
  const origins = await readOrigins();
  const known = await segments();
  for (const [slug, entry] of Object.entries(bySlug)) {
    entry.takes.sort((a, b) => b.take - a.take);
    entry.selected = selected[slug] ?? entry.takes[0]?.take ?? null;
    const now = textStamp(known.get(slug)?.text ?? "");
    for (const take of entry.takes) {
      const was = scripts[`${slug}.take${take.take}`];
      take.stale = was !== undefined && was !== now;
      take.coverage = reached[`${slug}.take${take.take}`] ?? null;
      // Takes made before the API existed were all read into a microphone.
      // Older files stored the origin as a bare string, with no voice.
      const made = origins[`${slug}.take${take.take}`];
      const record = typeof made === "string" ? { origin: made } : (made ?? {});
      take.origin = record.origin ?? "mic";
      take.voice = record.voice ?? null;
    }
    const chosen = entry.takes.find((t) => t.take === entry.selected);
    entry.stale = chosen?.stale ?? false;
    entry.origin = chosen?.origin ?? null;
    entry.voice = chosen?.voice ?? null;
  }
  await saveLengths();
  return bySlug;
}

async function elevenSpeak(text, voice, settings) {
  const res = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voice.id}?output_format=mp3_44100_128`,
    {
      method: "POST",
      headers: {
        "xi-api-key": ELEVEN_KEY,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        text,
        model_id: ELEVEN_MODEL,
        voice_settings: settings,
        // The dictionary is made and edited in the ElevenLabs interface. No
        // version is sent, so the latest one is used and an edit there takes
        // effect on the next take with nothing to do here.
        ...(ELEVEN_DICTIONARY
          ? {
              pronunciation_dictionary_locators: [
                { pronunciation_dictionary_id: ELEVEN_DICTIONARY },
              ],
            }
          : {}),
      }),
    },
  );
  if (!res.ok)
    throw new Error(`synthesis failed: ${res.status} ${await res.text()}`);
  return Buffer.from(await res.arrayBuffer());
}

// Whatever arrives — microphone WAV or MP3 from the API — becomes the one shape
// the pipeline reads, mono MP3 at BITRATE, filed as the next take and chosen.
async function storeTake({ slug, active, bytes, ext, origin, voice }) {
  await mkdir(TAKES_DIR, { recursive: true });
  const next = ((await takeFiles(slug))[0] ?? 0) + 1;

  const raw = join(TAKES_DIR, `.incoming-${next}${ext}`);
  await writeFile(raw, bytes);
  const take = join(TAKES_DIR, `${slug}.take${next}.mp3`);
  try {
    await run("ffmpeg", [
      "-hide_banner",
      "-loglevel",
      "error",
      "-y",
      "-i",
      raw,
      "-af",
      LEAD_FILTER,
      "-codec:a",
      "libmp3lame",
      "-b:a",
      BITRATE,
      "-ac",
      "1",
      take,
    ]);
  } finally {
    await unlink(raw).catch(() => {});
  }

  await clearActive(slug);
  await copyFile(take, join(AUDIO_DIR, active));
  const selected = await readSelected();
  selected[slug] = next;
  await saveSelected(selected);

  const key = `${slug}.take${next}`;
  const scripts = await readScripts();
  scripts[key] = textStamp(await segmentText(slug));
  await writeFile(SCRIPTS, JSON.stringify(scripts, null, 2));

  const origins = await readOrigins();
  origins[key] = voice ? { origin, voice } : { origin };
  await writeFile(ORIGINS, JSON.stringify(origins, null, 2));

  return next;
}

const server = createServer(async (req, res) => {
  if (req.method === "GET" && (req.url === "/" || req.url === "")) {
    res.writeHead(302, { location: "/record-audio.html" }).end();
    return;
  }
  if (req.method === "GET" && req.url.startsWith("/respell?")) {
    const word = new URL(req.url, "http://x").searchParams.get("w") ?? "";
    if (!/^[\p{L}\p{N}'\u2019-]{1,40}$/u.test(word)) {
      res.writeHead(400).end("bad word");
      return;
    }
    try {
      const { stdout } = await run("espeak-ng", [
        "-q",
        "--ipa",
        "-v",
        "en-us",
        word,
      ]);
      const { respell } = await import("./respell.mjs");
      res.writeHead(200, {
        "content-type": "application/json",
        "cache-control": "no-store",
      });
      res.end(JSON.stringify({ word, say: respell(stdout.trim()) }));
    } catch (err) {
      res.writeHead(500).end(String(err.message));
    }
    return;
  }

  if (req.method === "GET" && req.url.startsWith("/say.mp3?")) {
    const word = new URL(req.url, "http://x").searchParams.get("w") ?? "";
    if (!/^[\p{L}\p{N}'\u2019-]{1,40}$/u.test(word)) {
      res.writeHead(400).end("bad word");
      return;
    }
    try {
      const body = await speak(word);
      res.writeHead(200, {
        "content-type": "audio/mpeg",
        "cache-control": "no-store",
        "content-length": body.length,
      });
      res.end(body);
    } catch (err) {
      res
        .writeHead(err.code === "ENOVOICE" ? 503 : 500)
        .end(String(err.message));
    }
    return;
  }

  if (req.method === "GET" && /^\/reference\/[\w-]+\.mp3$/.test(req.url)) {
    const slug = req.url.slice("/reference/".length).replace(/\.mp3$/, "");
    try {
      const body = await reference(slug);
      res.writeHead(200, {
        "content-type": "audio/mpeg",
        "cache-control": "no-store",
        "content-length": body.length,
      });
      res.end(body);
    } catch (err) {
      res
        .writeHead(err.code === "ENOVOICE" ? 503 : 404)
        .end(String(err.message));
    }
    return;
  }

  if (req.method === "GET" && req.url.startsWith("/audio-status")) {
    const body = JSON.stringify(await audioStatus());
    res.writeHead(200, {
      "content-type": "application/json",
      "cache-control": "no-store",
    });
    res.end(body);
    return;
  }

  if (req.method === "PUT" && /^\/audio\/[\w.-]+$/.test(req.url)) {
    const file = req.url.slice("/audio/".length);
    const slug = slugOf(file);
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const next = await storeTake({
      slug,
      active: `${file.replace(/\.[^.]+$/, "")}.mp3`,
      bytes: Buffer.concat(chunks),
      ext: ".wav",
      origin: "mic",
    });

    res.writeHead(204).end();
    console.log(`saved ${slug} as take ${next} (mic)`);
    measureTake(slug, next);
    return;
  }

  if (req.method === "GET" && req.url === "/voice-settings") {
    res.writeHead(200, {
      "content-type": "application/json",
      "cache-control": "no-store",
    });
    const config = await readVoiceConfig();
    res.end(
      JSON.stringify({
        settings: config.settings,
        range: ELEVEN_RANGE,
        voice: config.voice.id,
        voices: ELEVEN_VOICES,
        ready: Boolean(ELEVEN_KEY),
      }),
    );
    return;
  }

  if (req.method === "PUT" && req.url === "/voice-settings") {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const wanted = JSON.parse(Buffer.concat(chunks).toString() || "{}");
    const config = await readVoiceConfig();
    const saved = { ...config.settings, voice: config.voice.id };
    for (const [name, [low, high]] of Object.entries(ELEVEN_RANGE)) {
      const value = Number(wanted[name]);
      if (Number.isFinite(value))
        saved[name] = Math.min(high, Math.max(low, value));
    }
    if (ELEVEN_VOICES.some((v) => v.id === wanted.voice))
      saved.voice = wanted.voice;
    await mkdir(TAKES_DIR, { recursive: true });
    await writeFile(VOICE_SETTINGS, JSON.stringify(saved, null, 2));
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(saved));
    return;
  }

  if (req.method === "POST" && req.url === "/synthesize") {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = JSON.parse(Buffer.concat(chunks).toString() || "{}");
    const slug = String(body.slug ?? "").replace(/[^\w-]/g, "");
    const active = String(body.active ?? `${slug}.mp3`).replace(/[^\w.-]/g, "");
    if (!ELEVEN_KEY) {
      res.writeHead(503).end("ELEVENLABS_API_KEY is not set");
      return;
    }
    const text = await segmentText(slug);
    if (!text) {
      res.writeHead(404).end("no such segment");
      return;
    }
    const { settings, voice } = await readVoiceConfig();
    try {
      const next = await storeTake({
        slug,
        active,
        bytes: await elevenSpeak(text, voice, settings),
        ext: ".mp3",
        origin: "api",
        voice: voice.label,
      });
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ take: next }));
      console.log(`saved ${slug} as take ${next} (${voice.label})`);
      measureTake(slug, next);
    } catch (err) {
      console.warn(`${slug}: ${err.message}`);
      res.writeHead(502).end(err.message);
    }
    return;
  }

  if (req.method === "POST" && req.url.startsWith("/takes/")) {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = JSON.parse(Buffer.concat(chunks).toString() || "{}");
    const action = req.url.slice("/takes/".length).split("?")[0];
    const slug = String(body.slug ?? "").replace(/[^\w-]/g, "");
    const take = Number(body.take);
    const active = String(body.active ?? `${slug}.wav`).replace(/[^\w.-]/g, "");
    if (!slug || !Number.isFinite(take)) {
      res.writeHead(400).end("bad request");
      return;
    }
    const selected = await readSelected();

    if (action === "select") {
      await clearActive(slug);
      await copyFile(await takePath(slug, take), join(AUDIO_DIR, active));
      selected[slug] = take;
      await saveSelected(selected);
      console.log(`selected ${slug} take ${take}`);
    } else if (action === "delete") {
      await unlink(await takePath(slug, take)).catch(() => {});
      if (selected[slug] === take) {
        await clearActive(slug);
        const left = await takeFiles(slug);
        if (left.length) {
          await copyFile(
            await takePath(slug, left[0]),
            join(AUDIO_DIR, active),
          );
          selected[slug] = left[0];
        } else delete selected[slug];
        await saveSelected(selected);
      }
      console.log(`deleted ${slug} take ${take}`);
    } else {
      res.writeHead(404).end("unknown action");
      return;
    }
    res.writeHead(204).end();
    return;
  }

  const target = resolvePath(req.url);
  if (!target || !target.file.startsWith(target.dir)) {
    res.writeHead(403).end("forbidden");
    return;
  }

  try {
    const info = await stat(target.file);
    if (info.isDirectory()) throw new Error("directory");
    let body = await readFile(target.file);
    if (target.file.endsWith("2026-spanning-tree.js"))
      body = Buffer.concat([body, Buffer.from(EPILOGUE)]);
    res.writeHead(200, {
      "content-type": TYPES[extname(target.file)] ?? "application/octet-stream",
      "cache-control": "no-store",
      "content-length": body.length,
    });
    res.end(req.method === "HEAD" ? undefined : body);
  } catch {
    res.writeHead(404).end("not found");
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`stage      http://127.0.0.1:${PORT}/stage.html?segment=001`);
  console.log(`recorder   http://127.0.0.1:${PORT}/record-audio.html`);
  if (ELEVEN_KEY)
    console.log(
      `voice      ${ELEVEN_VOICE.name}${ELEVEN_DICTIONARY ? `, dictionary ${ELEVEN_DICTIONARY}` : ", no dictionary"}`,
    );
});
