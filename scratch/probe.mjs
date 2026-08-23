// Checks that the headless browser gives us real pixels: colour emoji, the site
// fonts, and a non-blank frame at 1920x1080.

import { createServer } from "node:http";
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { browser } from "./cdp.mjs";

// Paths are anchored to this file, not to the working directory, so the scripts
// run the same from scratch/ or anywhere else.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

const PAGE = `<!doctype html><meta charset="utf-8">
<style>
  html, body { margin: 0; height: 100%; }
  body {
    background: #101418; color: #e8eaed;
    font: 500 40px/1.5 system-ui, sans-serif;
    display: grid; place-content: center; gap: 24px; text-align: center;
  }
  .emoji { font-size: 96px; letter-spacing: 24px; }
  .swatch { display: flex; justify-content: center; }
  .swatch i { width: 120px; height: 80px; }
</style>
<div>Spanning tree probe — 1920&times;1080</div>
<div class="emoji">&#127795;&#128187;&#128424;&#128224;&#128250;</div>
<div class="swatch">
  <i style="background:#e34"></i><i style="background:#2a7"></i>
  <i style="background:#fc0"></i><i style="background:#48f"></i>
</div>
<div style="font-family: ui-monospace, monospace; font-size: 28px">
  02:00:00:00:00:01 &middot; 0x8002 &middot; 32,768
</div>`;

const PORT = 8099;
const server = createServer((_, res) => {
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(PAGE);
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));

const b = await browser();
console.log("browser:", b.version.Browser);

const page = await b.open(`http://127.0.0.1:${PORT}/`);
await page.send("Page.enable");
await page.once("Page.loadEventFired");
await page.send("Emulation.setDeviceMetricsOverride", {
  width: 1920,
  height: 1080,
  deviceScaleFactor: 1,
  mobile: false,
});
// Let the fonts settle before the shot.
await page.send("Runtime.evaluate", {
  expression: "document.fonts.ready.then(() => 1)",
  awaitPromise: true,
});
const { data } = await page.send("Page.captureScreenshot", { format: "png" });
writeFileSync(join(HERE, "out/probe.png"), Buffer.from(data, "base64"));
console.log(
  "wrote scratch/out/probe.png",
  Buffer.from(data, "base64").length,
  "bytes",
);

await page.close();
b.close();
server.close();
