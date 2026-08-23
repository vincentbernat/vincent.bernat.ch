// Renders segments to frames, by driving the stage in a headless browser.
//
//   node scratch/record.mjs --all
//   node scratch/record.mjs --segment 042
//   node scratch/record.mjs --section electing-the-root-bridge
//   node scratch/record.mjs --segment 042 --preview     (one frame, no video)
//   node scratch/record.mjs --all --force               (ignore the cache)
//
// A segment where nothing moves is one still frame; ffmpeg stretches it later.
// A segment with an animated cue is captured frame by frame off a clock this
// script turns by hand, so the render never races the wall clock and comes out
// the same every time.

import { execFileSync, spawn } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { once } from "node:events";
import { dirname, join } from "node:path";
import * as align from "./align.mjs";
import { browser } from "./cdp.mjs";
import { openStage, evaluate, shoot } from "./shot.mjs";
import { planRuns } from "./runs.mjs";

import { fileURLToPath } from "node:url";

// Paths are anchored to this file, not to the working directory, so the scripts
// run the same from scratch/ or anywhere else.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

const OUT = join(HERE, "out");
// Motion segments go straight to video: at 1080p a PNG frame is about 110 kB,
// so keeping them on disk would cost several gigabytes for one render.
const CLIPS = join(OUT, "clips-raw");
const STILLS = join(OUT, "stills");
// Where the narration lives. Point AUDIO_DIR elsewhere to cut against
// placeholder takes without touching the real ones.
const AUDIO = process.env.AUDIO_DIR ?? join(HERE, "audio");
const MANIFEST = join(OUT, "render.json");

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const value = (name) => {
  const i = args.indexOf(name);
  return i < 0 ? null : args[i + 1];
};

const data = JSON.parse(readFileSync(join(HERE, "out/segments.json"), "utf8"));
const FPS = data.fps;
const PRESET = process.env.X264_PRESET ?? "veryfast";
const CRF = process.env.X264_CRF ?? "12";
const FRAME_MS = 1000 / FPS;
const LOOP_GAP = data.loopGap ?? 1.2;
const GAP = data.segmentGap ?? 0.45;

// How long a replay may run past the narration before we cut anyway.
const OVERRUN_LIMIT = 8;

// How long the closing iris takes to shut.
const IRIS_MS = 1000;

// -- durations ---------------------------------------------------------

function audioFor(segment) {
  if (segment.audio) return existsSync(segment.audio) ? segment.audio : null;
  if (!existsSync(AUDIO)) return null;
  // Matched on the slug, not the number in front of it: editing the script
  // renumbers segments, and a recording should not be orphaned by that.
  const match = readdirSync(AUDIO).find(
    (f) => f.replace(/^\d+-/, "").replace(/\.[^.]+$/, "") === segment.slug,
  );
  return match ? join(AUDIO, match) : null;
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

// What the segment should last, and where that number came from.
// Time added after the narration, for a diagram to keep moving once the words
// have stopped.
function durationOf(segment) {
  const found = baseDuration(segment);
  const tail = segment.tail ?? 0;
  return tail ? { ...found, seconds: found.seconds + tail } : found;
}

function baseDuration(segment) {
  if (segment.durationOverride)
    return { seconds: segment.durationOverride, from: "override" };
  const audio = audioFor(segment);
  if (audio) return { seconds: probeDuration(audio), from: "audio", audio };
  if (segment.holdOverride)
    return { seconds: segment.holdOverride, from: "override" };
  if (segment.hold) return { seconds: segment.hold, from: "hold" };
  if (segment.estimate) return { seconds: segment.estimate, from: "estimate" };
  return { seconds: 3, from: "default" };
}

// -- the cache ---------------------------------------------------------

// What a frame looks like depends on more than the segment: the stage, the
// widget's own CSS and JavaScript, the mark in the corner. None of that is in
// segments.json, so it is hashed here. Change any of it and every clip is
// rendered again, which is what happened when the bridges gained a second line
// and when the corner mark arrived.
const APPEARANCE = [
  join(HERE, "stage.html"),
  join(HERE, "stage.css"),
  join(HERE, "stage.mjs"),
  join(REPO, "content/media/css/2026-spanning-tree.css"),
  join(REPO, "content/media/js/2026-spanning-tree.js"),
  join(REPO, "content/media/images/favicon.svg"),
];

const stageStamp = createHash("sha256")
  .update(
    APPEARANCE.map((file) =>
      existsSync(file) ? readFileSync(file, "utf8") : "",
    ).join("\0"),
  )
  .digest("hex")
  .slice(0, 12);

// A segment is re-rendered when what it shows or how long it lasts changes.
function fingerprint(segment, seconds) {
  return createHash("sha256")
    .update(
      JSON.stringify({
        visual: segment.visual,
        credit: segment.credit,
        iris: segment.iris,
        cue: segment.cue,
        inherit: segment.inherit,
        autorun: segment.autorun,
        extraCues: segment.extraCues,
        text: segment.text,

        warmup: 0,
        fps: FPS,
        crf: CRF,
        loopGap: segment.loopGap ?? LOOP_GAP,
        gap: GAP,
        stage: stageStamp,
      }),
    )
    .digest("hex")
    .slice(0, 16);
}

const manifest = existsSync(MANIFEST)
  ? JSON.parse(readFileSync(MANIFEST, "utf8"))
  : {};

// -- encoding ----------------------------------------------------------

// An ffmpeg reading PNG frames on stdin and writing one segment's video. The
// trailing gap is part of the clip, held on the last frame, so assembly can
// copy the video through without re-encoding it.
function startEncoder(file) {
  const proc = spawn(
    "ffmpeg",
    [
      "-hide_banner",
      "-loglevel",
      "error",
      "-y",
      "-f",
      "image2pipe",
      "-framerate",
      String(FPS),
      "-i",
      "-",
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
      file,
    ],
    { stdio: ["pipe", "ignore", "inherit"] },
  );
  const failure = new Promise((_, reject) =>
    proc.on("error", (err) => reject(new Error(`ffmpeg: ${err.message}`))),
  );
  return {
    async write(buffer) {
      if (proc.stdin.write(buffer)) return;
      // Encoding is slower than capture, so wait rather than buffer the whole
      // segment in memory.
      await Promise.race([once(proc.stdin, "drain"), failure]);
    },
    async finish() {
      proc.stdin.end();
      const [code] = await Promise.race([once(proc, "close"), failure]);
      if (code !== 0) throw new Error(`ffmpeg exited with ${code}`);
    },
  };
}

// Whether what was rendered can still serve, given how long the segment now
// needs to be.
//
// A still is stretched at assembly, so its length never matters. Anything
// longer than what was rendered has to be rendered again: there are no frames
// to invent. Anything shorter can be cut, but only where the diagram is at
// rest — cutting a step animation mid-flight is exactly what the render goes
// out of its way to avoid.
function fits(previous, seconds) {
  if (previous.still) return true;
  if (previous.seconds === undefined) return false;
  if (seconds > previous.seconds + 0.05) return false;
  if (previous.seconds - seconds <= 0.05) return true;
  if (previous.mode !== "step") return true;
  return (previous.quiet ?? []).some(
    ([from, to]) => seconds >= from && seconds <= to,
  );
}

// -- capture -----------------------------------------------------------

// The control link a segment plays, if any. A segment with no link of its own
// either replays the last one on its diagram, to hold the state the prose is
// talking about, or simply starts the simulation.
function specFor(segment) {
  // Only a stage showing a diagram has anything to drive.
  if (segment.visual.type !== "topology") return null;
  if (segment.cue) return segment.cue.spec;
  if (segment.inherit) return segment.inherit.spec;
  if (segment.autorun) return "...";
  return null;
}

async function captureStill(page, segment) {
  const spec = specFor(segment);
  if (spec) {
    await evaluate(page, "window.__stage.freeze()", true);
    await evaluate(page, `window.__stage.fireCue(${JSON.stringify(spec)})`);
    // Let the replay finish, so the frame shows where it ends up rather than
    // the moment before it starts.
    const spent = await evaluate(page, `window.__stage.settle(${FRAME_MS})`);
    if (spent >= 30000)
      console.warn(
        `  ${segment.id}: never settled, frame may be mid-animation`,
      );
  }
  writeFileSync(join(STILLS, `${segment.slug}.png`), await shoot(page));
  return { frames: 1, quiet: [] };
}

// The closing iris: a black plane over the frame with a round hole on one
// sprite, shut over the last second. It lives here rather than in the stage
// because it belongs to the take, not to how a segment looks, and because
// anything the stage files touch re-renders the whole video.
//
// The hole follows the sprite, so it lands wherever the character walked to.
const irisStep = (selector, progress) => `(() => {
  let el = document.getElementById("iris");
  if (!el) {
    el = document.createElement("div");
    el.id = "iris";
    el.style.cssText = "position:fixed;border-radius:50%;pointer-events:none;" +
      "box-shadow:0 0 0 2400px #000;transform:translate(-50%,-50%)";
    document.body.append(el);
  }
  const host = document.querySelector(".mstp-host");
  const box = (host?.shadowRoot ?? document)
    .querySelector(${JSON.stringify(selector)})
    ?.getBoundingClientRect();
  const x = box ? box.left + box.width / 2 : innerWidth / 2;
  const y = box ? box.top + box.height / 2 : innerHeight / 2;
  // Far enough to clear the furthest corner, so nothing shows at the start.
  const far = Math.hypot(
    Math.max(x, innerWidth - x),
    Math.max(y, innerHeight - y),
  );
  const p = Math.min(1, Math.max(0, ${progress}));
  const size = 2 * far * (1 - p * p * (3 - 2 * p));
  el.style.left = x + "px";
  el.style.top = y + "px";
  el.style.width = size + "px";
  el.style.height = size + "px";
})()`;

async function captureMotion(page, segment, seconds, options = {}) {
  const {
    file = join(CLIPS, `${segment.slug}.mp4`),
    hold = true,
    iris = null,
  } = options;
  const gap = (segment.loopGap ?? LOOP_GAP) * 1000;
  const planned = Math.max(1, Math.round(seconds * FPS));
  const mode = segment.cue?.mode ?? "none";

  const spec = specFor(segment);
  await evaluate(page, "window.__stage.freeze()", true);
  if (spec)
    await evaluate(page, `window.__stage.fireCue(${JSON.stringify(spec)})`);
  const encoder = startEncoder(file);
  const total = planned * FRAME_MS;
  const quiet = [];
  let restedAt = null;
  let frames = 0;
  let idleSince = null;
  // How long one play takes, learnt from the first one. A replay only starts
  // when there is room for it to finish before the narration does, so the
  // segment never has to overrun and never cuts mid-flight.
  let playLength = null;
  let elapsed = 0;

  for (;;) {
    const still = await evaluate(page, `window.__stage.tick(${FRAME_MS})`);
    elapsed += FRAME_MS;

    // A step cue plays once and stops. While the narration is still going,
    // start it again so the diagram is not frozen under the words.
    if (still && restedAt === null) restedAt = elapsed;
    if (!still && restedAt !== null) {
      quiet.push([restedAt / 1000, elapsed / 1000]);
      restedAt = null;
    }

    if (mode === "step") {
      if (still) {
        if (idleSince === null) {
          idleSince = elapsed;
          if (playLength === null) playLength = elapsed;
        } else if (
          elapsed - idleSince >= gap &&
          elapsed + gap + playLength <= total
        ) {
          await evaluate(
            page,
            `window.__stage.fireCue(${JSON.stringify(spec)})`,
          );
          idleSince = null;
        }
      } else {
        idleSince = null;
      }
    }

    if (iris) {
      const left = total - elapsed;
      await evaluate(
        page,
        irisStep(iris, left >= IRIS_MS ? 0 : 1 - left / IRIS_MS),
      );
    }

    await encoder.write(await shoot(page));
    frames++;

    if (frames < planned) continue;
    // Past the narration: stop on a still diagram rather than mid-flight.
    if (mode !== "step") break;
    if (idleSince !== null) break;
    if (frames >= planned + OVERRUN_LIMIT * FPS) {
      console.warn(
        `  ${segment.id}: still moving after ${OVERRUN_LIMIT}s of overrun, cutting`,
      );
      break;
    }
  }
  if (restedAt !== null) quiet.push([restedAt / 1000, elapsed / 1000]);
  if (hold) frames += await holdLastFrame(page, encoder);
  await encoder.finish();
  return { frames, quiet };
}

// The pause between segments, held on the last frame so it reads as a beat
// rather than a cut.
async function holdLastFrame(page, encoder) {
  const extra = Math.round(GAP * FPS);
  if (extra <= 0) return 0;
  const frame = await shoot(page);
  for (let i = 0; i < extra; i++) await encoder.write(frame);
  return extra;
}

// The poem runs to Radia's own recording, so its lines light up on timings taken
// from that file: whisper says when each line starts, the same way subtitles are
// timed everywhere else.
function poemMarks(segment, seconds) {
  const audio =
    segment.audio && existsSync(segment.audio) ? segment.audio : null;
  if (!audio || !align.available()) return [];
  try {
    return align.lineTimes(segment.slug, audio, segment.visual.lines, seconds);
  } catch (err) {
    console.warn(`  ${segment.id}: cannot time the poem (${err.message})`);
    return [];
  }
}

async function capturePoem(page, segment, seconds) {
  const encoder = startEncoder(join(CLIPS, `${segment.slug}.mp4`));
  const marks = poemMarks(segment, seconds);
  const planned = Math.max(1, Math.round(seconds * FPS));
  await evaluate(page, "window.__stage.freeze()", true);

  let current = -1;
  for (let frame = 0; frame < planned; frame++) {
    const at = (frame * FRAME_MS) / 1000;
    let line = -1;
    for (let i = 0; i < marks.length; i++) if (at >= marks[i]) line = i;
    if (line !== current) {
      await evaluate(page, `window.__stage.poemLine(${line})`);
      current = line;
    }
    await evaluate(page, `window.__stage.advance(${FRAME_MS})`);
    await encoder.write(await shoot(page));
  }
  const extra = await holdLastFrame(page, encoder);
  await encoder.finish();
  return { frames: planned + extra, quiet: [] };
}

// -- main ---------------------------------------------------------------

function missing(what) {
  console.error(`no ${what}. Names come from out/segments.json.`);
  process.exit(2);
}

function selection() {
  if (value("--segment")) {
    const wanted = value("--segment");
    const picked = data.segments.filter(
      (s) => s.id === wanted || s.slug === wanted,
    );
    if (!picked.length) return missing(`segment "${wanted}"`);
    return picked;
  }
  if (value("--section")) {
    const wanted = value("--section");
    const picked = data.segments.filter((s) => s.sectionSlug === wanted);
    if (!picked.length) return missing(`section "${wanted}"`);
    return picked;
  }
  if (flag("--all")) return data.segments.filter((s) => !s.skip);
  console.error(
    "usage: record.mjs --all | --segment <id|slug> | --section <slug>",
  );
  console.error("       --preview  one frame, no video");
  console.error("       --force    render even when the cache says otherwise");
  process.exit(2);
}

const { runs, runOf } = planRuns(
  data.segments,
  (s) => durationOf(s).seconds,
  GAP,
);

function runFingerprint(run) {
  return createHash("sha256")
    .update(
      JSON.stringify({
        topology: run.topology,
        section: run.section,
        credit: run.members[0].credit,
        iris: run.members[run.members.length - 1].iris ?? null,
        fps: FPS,
        crf: CRF,
        stage: stageStamp,
      }),
    )
    .digest("hex")
    .slice(0, 16);
}

const chosen = selection();
if (!chosen.length) {
  console.error("nothing selected");
  process.exit(1);
}

mkdirSync(CLIPS, { recursive: true });
mkdirSync(STILLS, { recursive: true });
const b = await browser();
// A run that was interrupted leaves its tab behind, still running a widget and
// its animation loop. Enough of them and the next render starts timing out on
// screenshots, so clear them before starting.
// This browser exists only to be driven, so anything left pointing at a local
// page is from a run that did not finish. A leftover tab keeps a widget and its
// animation loop alive, and enough of them starve the next render.
const stale = (await b.pages()).filter((p) =>
  /^https?:\/\/(127\.0\.0\.1|localhost):/.test(p.url),
);
for (const page of stale) await b.closeTarget(page.id);
if (stale.length) console.log(`closed ${stale.length} leftover tab(s)`);
console.log(
  `browser ${b.version.Browser}, ${chosen.length} segment(s) at ${FPS} fps\n`,
);

let rendered = 0;
let skipped = 0;
const failed = [];
const started = Date.now();

// A run is rendered the first time one of its members comes up, and the rest
// then cut their piece out of it.
const runState = new Map();

async function renderRun(run) {
  // A run that failed stays failed for this pass. Without this every member
  // after the first tries it again, and a run of seven turns one failure into
  // seven, each paying the full timeout.
  if (runState.has(run.id)) {
    const state = runState.get(run.id);
    if (state.error) throw state.error;
    return state;
  }
  const key = runFingerprint(run);
  const file = join(CLIPS, `run-${run.id}.mp4`);
  const previous = manifest[`run:${run.id}`];
  // The clip only has to be long enough. Time moving between the members of a
  // run leaves the frames it already holds perfectly good.
  if (
    !flag("--force") &&
    previous?.key === key &&
    existsSync(file) &&
    run.total <= previous.seconds + 0.05
  ) {
    const state = { key, seconds: previous.seconds, reused: true };
    runState.set(run.id, state);
    return state;
  }

  let page;
  try {
    page = await openStage(b, run.members[0].slug);
  } catch (err) {
    runState.set(run.id, { error: err });
    throw err;
  }
  try {
    rmSync(file, { force: true });
    const result = await captureMotion(page, run.members[0], run.total, {
      file,
      hold: false,
      // A run ends where its last member ends, so an iris asked for there is
      // the one that closes the take.
      iris: run.members[run.members.length - 1].iris ?? null,
    });
    manifest[`run:${run.id}`] = {
      key,
      kind: "run",
      frames: result.frames,
      seconds: Number(run.total.toFixed(3)),
      members: run.members.map((member) => member.slug),
    };
    writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2));
    console.log(
      `run ${run.id.slice(0, 40).padEnd(40)} ${String(result.frames).padStart(5)} frames  ${run.total.toFixed(1)}s (${run.members.length} segments)`,
    );
    const state = { key, seconds: run.total, reused: false };
    runState.set(run.id, state);
    return state;
  } catch (err) {
    rmSync(file, { force: true });
    runState.set(run.id, { error: err });
    throw err;
  } finally {
    await page.close().catch(() => {});
  }
}

for (const segment of chosen) {
  const { seconds, from, audio } = durationOf(segment);
  const member = flag("--preview") ? undefined : runOf[segment.slug];
  const label = `${segment.id} ${segment.slug.slice(0, 40).padEnd(40)}`;

  if (member) {
    const run = runs.get(member.id);
    let state;
    try {
      state = await renderRun(run);
    } catch (err) {
      console.warn(`${label} FAILED (${err.message})`);
      failed.push(segment.slug);
      continue;
    }
    // Its own clip, from before it joined a run, is dead weight now.
    rmSync(join(CLIPS, `${segment.slug}.mp4`), { force: true });
    manifest[segment.slug] = {
      key: state.key,
      run: member.id,
      frames: Math.round(seconds * FPS),
      quiet: [],
      mode: "run",
      seconds: Number(seconds.toFixed(3)),
      from,
      audio: audio ?? null,
      still: false,
      slug: segment.slug,
    };
    writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2));
    if (state.reused) skipped++;
    else rendered++;
    console.log(
      `${label} ${seconds.toFixed(1)}s from run ${member.id.slice(0, 24)} at ${member.offset.toFixed(1)}s`,
    );
    continue;
  }

  const key = fingerprint(segment, seconds);

  const artefact = segment.static
    ? join(STILLS, `${segment.slug}.png`)
    : join(CLIPS, `${segment.slug}.mp4`);

  const previous = manifest[segment.slug];
  const reuse =
    !flag("--preview") &&
    !flag("--force") &&
    previous?.key === key &&
    existsSync(artefact) &&
    fits(previous, seconds);

  if (reuse) {
    const trimmed = !previous.still && previous.seconds - seconds > 0.05;
    console.log(
      `${label} cached${trimmed ? ` (trimmed from ${previous.seconds.toFixed(1)}s)` : ""}`,
    );
    skipped++;
    continue;
  }

  let page;
  try {
    page = await openStage(b, segment.slug);
  } catch (err) {
    console.warn(`${label} FAILED to open (${err.message})`);
    failed.push(segment.slug);
    continue;
  }

  if (flag("--preview")) {
    writeFileSync(join(OUT, `preview-${segment.slug}.png`), await shoot(page));
    console.log(`${label} -> ${OUT}/preview-${segment.slug}.png`);
    await page.close();
    continue;
  }

  rmSync(artefact, { force: true });

  let result;
  try {
    if (segment.visual.type === "poem")
      result = await capturePoem(page, segment, seconds);
    else if (segment.static) result = await captureStill(page, segment);
    else
      result = await captureMotion(page, segment, seconds, {
        iris: segment.iris ?? null,
      });
  } catch (err) {
    // One segment going wrong should not throw away everything rendered before
    // it. Note it, drop what it half-wrote, and carry on.
    console.warn(`${label} FAILED (${err.message})`);
    failed.push(segment.slug);
    rmSync(artefact, { force: true });
    delete manifest[segment.slug];
    continue;
  } finally {
    await page.close().catch(() => {});
  }

  manifest[segment.slug] = {
    key,
    frames: result.frames,
    quiet: result.quiet,
    mode: segment.static ? "still" : (segment.cue?.mode ?? "run"),
    seconds: Number(seconds.toFixed(3)),
    from,
    audio: audio ?? null,
    still: Boolean(segment.static),
    slug: segment.slug,
  };
  writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2));
  rendered++;
  console.log(
    `${label} ${String(result.frames).padStart(5)} frames  ${seconds.toFixed(1)}s (${from})`,
  );
}

b.close();
const took = Math.round((Date.now() - started) / 1000);
console.log(`\nrendered ${rendered}, cached ${skipped}, in ${took}s`);
if (failed.length) {
  console.log(`${failed.length} failed, run again to pick them up:`);
  for (const slug of failed) console.log(`  ${slug}`);
  process.exitCode = 1;
}
