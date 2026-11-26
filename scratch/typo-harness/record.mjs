// Record page.html in one browser as a 30 fps video.
//
//   node scratch/typo-harness/record.mjs <firefox|chromium|epiphany> <name> [query]
//
// The browser runs in its own Xvfb. The page sets each frame, then asks the
// server for a screenshot, so timing does not depend on the browser speed.
// The stage is found on screen with a magenta calibration frame.

import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const ROOT = path.resolve(HERE, "../..");
const FONTS = path.join(ROOT, "content/media/fonts");
const CHROMIUM =
  "/nix/store/l5fpsjzvsyqlj30qagkcgf9ikmbh9irr-chromium-157.0.8103.50/bin/chromium";
const SCREEN = { w: 1920, h: 1200 };
const DISPLAY = `:${process.env.XVFB_DISPLAY ?? 90 + Math.floor(Math.random() * 9)}`;
// Tools from /usr/bin break with the Nix libraries
const SYSTEM_ENV = { ...process.env };
delete SYSTEM_ENV.LD_LIBRARY_PATH;

const [browser, name, query = ""] = process.argv.slice(2);
if (!browser || !name) {
  console.error("usage: record.mjs <firefox|chromium|epiphany> <name> [query]");
  process.exit(1);
}
const outDir = path.join(HERE, "out");
const framesDir = path.join(outDir, `${name}-frames`);
fs.rmSync(framesDir, { recursive: true, force: true });
fs.mkdirSync(framesDir, { recursive: true });
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "typo-harness-"));

const children = [];
function start(cmd, args, opts = {}) {
  const child = spawn(cmd, args, { stdio: ["ignore", "ignore", "pipe"], ...opts });
  child.stderr.on("data", (d) => process.env.VERBOSE && process.stderr.write(d));
  children.push(child);
  return child;
}
function cleanup() {
  for (const child of children.reverse()) {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch {
      child.kill("SIGKILL");
    }
  }
  fs.rmSync(tmp, { recursive: true, force: true });
}
process.on("exit", cleanup);
process.on("SIGINT", () => process.exit(130));

function grab(x, y, w, h, args) {
  return spawnSync(
    "ffmpeg",
    [
      "-loglevel", "error",
      "-f", "x11grab", "-draw_mouse", "0",
      "-video_size", `${w}x${h}`,
      "-i", `${DISPLAY}+${x},${y}`,
      "-frames:v", "1",
      ...args,
    ],
    { env: SYSTEM_ENV, maxBuffer: 64 << 20 },
  );
}

// Position of the stage, from the bottom right corner of the magenta pixels
// on the screen, as window decorations may hide the top of the stage. Firefox
// may still show its splash when the page is ready, so try again for a while.
function calibrate(w, h) {
  for (let attempt = 0; attempt < 60; attempt++) {
    const box = findMagenta();
    if (box) return { x: box.x1 - w + 1, y: box.y1 - h + 1, w, h };
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 500);
  }
  grab(0, 0, SCREEN.w, SCREEN.h, ["-y", path.join(outDir, "calibration-failed.png")]);
  throw new Error("calibration frame not found, see out/calibration-failed.png");
}

function findMagenta() {
  const r = grab(0, 0, SCREEN.w, SCREEN.h, ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]);
  if (r.status !== 0) throw new Error(r.stderr.toString());
  const px = r.stdout;
  let x1 = -1, y1 = -1;
  for (let y = 0; y < SCREEN.h; y++) {
    for (let x = 0; x < SCREEN.w; x++) {
      const i = (y * SCREEN.w + x) * 3;
      if (px[i] === 255 && px[i + 1] === 0 && px[i + 2] === 255) {
        if (x > x1) x1 = x;
        if (y > y1) y1 = y;
      }
    }
  }
  if (x1 < 0) return null;
  return { x1, y1 };
}

const TYPES = {
  ".html": "text/html",
  ".json": "application/json",
  ".woff2": "font/woff2",
  ".css": "text/css",
  ".js": "text/javascript",
};
let rect = null;
let finished;
const done = new Promise((resolve, reject) => (finished = { resolve, reject }));

const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const route = url.pathname.slice(1);
  if (route === "calibrate") {
    rect = calibrate(Number(url.searchParams.get("w")), Number(url.searchParams.get("h")));
    console.log(`stage at ${rect.x},${rect.y}, ${rect.w}x${rect.h}`);
    return res.end("ok");
  }
  if (route === "frame") {
    const n = Number(url.searchParams.get("n"));
    const file = path.join(framesDir, `${String(n).padStart(5, "0")}.png`);
    const r = grab(rect.x, rect.y, rect.w, rect.h, ["-y", file]);
    if (r.status !== 0) return finished.reject(new Error(r.stderr.toString()));
    if (n % 30 === 0) process.stdout.write(`\rframe ${n}`);
    return res.end("ok");
  }
  if (route === "data") {
    const chunks = [];
    req.on("data", (d) => chunks.push(d));
    req.on("end", () => {
      fs.writeFileSync(path.join(outDir, `${name}.json`), Buffer.concat(chunks));
      res.end("ok");
    });
    return;
  }
  if (route === "log") {
    let body = "";
    req.on("data", (d) => (body += d));
    req.on("end", () => {
      console.log(body);
      res.end("ok");
    });
    return;
  }
  if (route === "done") {
    res.end("ok");
    return finished.resolve();
  }
  if (route === "error") {
    res.end("ok");
    return finished.reject(new Error(url.searchParams.get("m")));
  }
  const file = route.startsWith("fonts/")
    ? path.join(FONTS, path.basename(route))
    : route.startsWith("media/css/") || route.startsWith("media/js/")
      ? path.join(ROOT, "content", path.dirname(route), path.basename(route))
      : path.join(HERE, path.basename(route) || "page.html");
  fs.readFile(file, (err, data) => {
    if (err) {
      res.statusCode = 404;
      return res.end();
    }
    res.setHeader("Content-Type", TYPES[path.extname(file)] || "application/octet-stream");
    res.setHeader("Cache-Control", "no-store");
    res.end(data);
  });
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const label = { firefox: "Firefox", chromium: "Chromium", epiphany: "Epiphany" }[browser];
const page = `http://127.0.0.1:${server.address().port}/page.html?browser=${label}&${query}`;

start("Xvfb", [DISPLAY, "-screen", "0", `${SCREEN.w}x${SCREEN.h}x24`, "-nolisten", "tcp"], {
  env: SYSTEM_ENV,
  detached: true,
});
await new Promise((resolve) => setTimeout(resolve, 1000));
const env = { ...process.env, DISPLAY };

if (browser === "firefox") {
  const profile = path.join(tmp, "profile");
  fs.mkdirSync(profile);
  fs.writeFileSync(
    path.join(profile, "user.js"),
    [
      ["browser.shell.checkDefaultBrowser", false],
      ["browser.aboutwelcome.enabled", false],
      ["browser.startup.homepage_override.mstone", "ignore"],
      ["datareporting.policy.dataSubmissionEnabled", false],
      ["toolkit.telemetry.reportingpolicy.firstRun", false],
      ["datareporting.policy.dataSubmissionPolicyBypassNotification", true],
      ["browser.preonboarding.enabled", false],
      ["termsofuse.bypassNotification", true],
      ["termsofuse.acceptedVersion", 999],
      ["termsofuse.acceptedDate", String(Date.now())],
      ["layout.css.devPixelsPerPx", "1.0"],
    ]
      .map(([k, v]) => `user_pref(${JSON.stringify(k)}, ${JSON.stringify(v)});`)
      .join("\n"),
  );
  start("firefox", ["--no-remote", "--profile", profile, "--kiosk", page], {
    env,
    detached: true,
  });
} else if (browser === "chromium") {
  // Chromium downloads hyphenation dictionaries a few minutes after its first
  // start. Copy them from a profile where it did.
  const profile = path.join(tmp, "chromium");
  const dictionaries = path.join(HERE, "chromium-profile", "hyphen-data");
  if (!fs.existsSync(dictionaries)) throw new Error(`missing ${dictionaries}`);
  fs.cpSync(dictionaries, path.join(profile, "hyphen-data"), { recursive: true });
  start(
    CHROMIUM,
    [
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-features=Translate",
      "--force-device-scale-factor=1",
      "--window-position=0,0",
      `--window-size=${SCREEN.w},${SCREEN.h}`,
      "--kiosk",
      page,
    ],
    { env, detached: true },
  );
} else if (browser === "epiphany") {
  // Epiphany does not start with the Nix libraries in the environment
  const home = path.join(tmp, "home");
  fs.mkdirSync(home);
  start(
    "/usr/bin/dbus-run-session",
    ["--", "/usr/bin/epiphany", "--private-instance", page],
    {
      env: {
        PATH: "/usr/bin:/bin",
        HOME: home,
        DISPLAY,
        GDK_SCALE: "1",
        GDK_BACKEND: "x11",
        GTK_A11Y: "none",
        FONTCONFIG_FILE: process.env.FONTCONFIG_FILE ?? "",
        // The bubblewrap sandbox of WebKit does not start in the agent sandbox
        WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS: "1",
      },
      detached: true,
    },
  );
} else {
  throw new Error(`unknown browser ${browser}`);
}

const timeout = setTimeout(() => finished.reject(new Error("timeout")), 15 * 60 * 1000);
try {
  await done;
} finally {
  clearTimeout(timeout);
  server.close();
}
process.stdout.write("\n");

if (!fs.readdirSync(framesDir).length) {
  fs.rmdirSync(framesDir);
  process.exit(0);
}
// With DARK=1, the videos are dark, with the colors of "filter: invert(100%)
// hue-rotate(180deg)" used by the site in dark mode. The matrix of
// hue-rotate() comes from Filter Effects Module.
const hueRotate = (deg) => {
  const c = Math.cos((deg * Math.PI) / 180);
  const s = Math.sin((deg * Math.PI) / 180);
  return [
    [0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928],
    [0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.14, 0.072 - c * 0.072 - s * 0.283],
    [0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072],
  ];
};
const darkFilter = () => {
  const m = hueRotate(180);
  const mixer = ["r", "g", "b"]
    .flatMap((out, i) => ["r", "g", "b"].map((inp, j) => `${out}${inp}=${m[i][j].toFixed(4)}`))
    .join(":");
  return `format=rgb24,negate,colorchannelmixer=${mixer}`;
};

const encode = (video, filters) => {
  const r = spawnSync(
    "ffmpeg",
    [
      "-loglevel", "error", "-y",
      "-framerate", "30",
      "-i", path.join(framesDir, "%05d.png"),
      ...filters,
      // veryslow and animation give 40% smaller files for the same quality
      "-c:v", "libx264", "-preset", "veryslow", "-tune", "animation", "-crf", "16",
      // A keyframe at the start of each combination (3.5 seconds in
      // page.html), for faster seeks
      "-x264-params", "keyint=105:min-keyint=105:scenecut=0",
      "-pix_fmt", "yuv420p", "-movflags", "+faststart",
      video,
    ],
    { env: SYSTEM_ENV, stdio: "inherit" },
  );
  if (r.status !== 0) process.exit(r.status);
  console.log(video);
};
encode(path.join(outDir, `${name}.mp4`), process.env.DARK ? ["-vf", darkFilter()] : []);
process.exit(0);
