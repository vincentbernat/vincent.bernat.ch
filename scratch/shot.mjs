// One frame of one segment, to check how it looks.
//
//   node scratch/shot.mjs 025 [--cue] [--advance 2000]
//
// --cue fires the segment's control link first, --advance turns the virtual
// clock on and moves it that many milliseconds before the shot.

import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { browser } from "./cdp.mjs";

// Paths are anchored to this file, not to the working directory, so the scripts
// run the same from scratch/ or anywhere else.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

const args = process.argv.slice(2);
const wanted = args[0] ?? "001";
const withCue = args.includes("--cue");
const advanceMs = Number(args[args.indexOf("--advance") + 1]) || 0;
const PORT = Number(process.env.STAGE_PORT ?? 8081);

export async function openStage(b, segment) {
  const page = await b.open("about:blank");
  await page.send("Page.enable");
  await page.send("Runtime.enable");
  page.on("Runtime.consoleAPICalled", (ev) => {
    if (ev.type === "error" || ev.type === "warning")
      console.log(
        `  [page ${ev.type}]`,
        ev.args.map((a) => a.value ?? a.description).join(" "),
      );
  });
  await page.send("Emulation.setDeviceMetricsOverride", {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await page.send("Emulation.setEmulatedMedia", {
    features: [
      { name: "prefers-color-scheme", value: "light" },
      // Frames are captured off a clock we turn by hand, and with
      // requestAnimationFrame replaced the browser never runs a rendering tick,
      // so CSS animations never start, never end, and never fire animationend.
      // The widget cleans up after its state-change slide in that handler, so
      // its ghost copy of the diagram would sit over the real one for the rest
      // of the segment. Reduced motion is the widget's own way of skipping the
      // slide, the clock bump and the waiting hourglass. The BPDUs are animated
      // from requestAnimationFrame and are not affected.
      { name: "prefers-reduced-motion", value: "reduce" },
    ],
  });
  await page.send("Page.navigate", {
    url: `http://127.0.0.1:${PORT}/stage.html?segment=${segment}`,
  });
  // Asked for again and again rather than waited for inside the page. A wait
  // set up before the navigation commits belongs to the old document, and is
  // thrown away with it: nothing ever resolves it, and worse, a wait that does
  // resolve on the old page hands back a window with no stage on it.
  const deadline = Date.now() + 40000;
  for (;;) {
    const state = await page
      .send("Runtime.evaluate", {
        expression: `window.__stage ? "ready" : (window.__stageError ?? "")`,
        returnByValue: true,
      })
      .then(({ result }) => result.value ?? "")
      .catch(() => "");
    if (state === "ready") break;
    if (state) throw new Error(state);
    if (Date.now() > deadline) throw new Error("stage timed out");
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return page;
}

export async function evaluate(page, expression, awaitPromise = false) {
  const { result, exceptionDetails } = await page.send("Runtime.evaluate", {
    expression,
    awaitPromise,
    returnByValue: true,
  });
  if (exceptionDetails)
    throw new Error(
      exceptionDetails.exception?.description ?? exceptionDetails.text,
    );
  return result.value;
}

// A screenshot can time out when the browser is busy — another tab left open
// by an interrupted run is enough. Losing an hour of rendering to one slow
// frame is not worth it, so try again before giving up.
export async function shoot(page, attempts = 3) {
  for (let attempt = 1; ; attempt++) {
    try {
      const { data } = await page.send("Page.captureScreenshot", {
        format: "png",
        optimizeForSpeed: true,
      });
      return Buffer.from(data, "base64");
    } catch (err) {
      if (attempt >= attempts) throw err;
      console.warn(`  screenshot failed (${err.message}), retrying`);
    }
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const b = await browser();
  const page = await openStage(b, wanted);

  if (withCue) {
    const spec = await evaluate(
      page,
      "window.__stage.segment.cue?.spec ?? null",
    );
    if (spec) {
      console.log("cue:", spec);
      await evaluate(page, "window.__stage.freeze()");
      await evaluate(page, `window.__stage.fireCue(${JSON.stringify(spec)})`);
    } else {
      console.log("segment has no cue");
    }
  }
  if (advanceMs) {
    if (!withCue) await evaluate(page, "window.__stage.freeze()");
    await evaluate(
      page,
      `(() => { for (let t = 0; t < ${advanceMs}; t += 1000 / 60) window.__stage.advance(1000 / 60); })()`,
    );
    console.log(
      "state:",
      JSON.stringify(await evaluate(page, "window.__stage.state()")),
    );
  }

  mkdirSync(join(HERE, "out"), { recursive: true });
  const file = join(HERE, `out/shot-${wanted}.png`);
  writeFileSync(file, await shoot(page));
  console.log("wrote", file);
  await page.close();
  b.close();
}
