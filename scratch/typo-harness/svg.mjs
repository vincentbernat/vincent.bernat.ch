// Build the line-breaking animations from the layouts recorded by page.html.
//
//   node scratch/typo-harness/svg.mjs
//
// It writes one SVG for all the animations, with the layouts and the player of
// svg-player.js. The fragment of its URL selects the animation (#firefox,
// #chrome, #webkit, #preprocess): each one has a row of the SVG and a view
// showing it. It works on its own, content/media/js/wip.js adds the controls.
// Without script, like in an image, the first frame of the row is shown.

import fs from "node:fs";

const HERE = new URL(".", import.meta.url);
const ROOT = new URL("../../", import.meta.url);
const ANIMATIONS = [
  ["firefox-plain", "Firefox 160", "firefox"],
  ["chromium-plain", "Chromium 157", "chrome"],
  ["epiphany-plain", "WebKitGTK 2.54", "webkit"],
  ["firefox-processed", "Firefox 160", "preprocess"],
];
const SHY = "\u00ad";

// Same geometry as page.html
const pad = 24;
const label = 36;
const lines = 4;
const lineHeight = 30;
const baseline = 23.69;

const escape = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const strip = (s) => s.split(SHY).join("");

const player = fs.readFileSync(new URL("svg-player.js", HERE), "utf8");
if (player.includes("]]>")) throw new Error("player cannot go in CDATA");

const animations = {};
const frames = [];
const views = [];
const textChars = new Set("-");
const captionChars = new Set(
  "· hyphens: none auto manual text-align: justify text-wrap: pretty 0123456789px",
);
let size = null;
for (const [input, browser, name] of ANIMATIONS) {
  const data = JSON.parse(
    fs.readFileSync(new URL(`out/${input}-layout.json`, HERE), "utf8"),
  );
  const words = [];
  const separators = [];
  const re = /[^ \u00a0\u202f]+/g;
  for (let m, last = null; (m = re.exec(data.text)); last = m) {
    words.push(m[0]);
    if (last)
      separators.push(data.text.slice(last.index + last[0].length, m.index));
  }
  const widths = data.widths;
  const frame = Math.ceil(widths[0] * 1.1) + 2 * pad;
  const width = frame + (frame % 2);
  const height = lines * lineHeight + label + 2 * pad;

  // A repeated layout is replaced by 0
  const combos = data.combos.map((combo) => {
    let previous = null;
    const layouts = combo.layouts.map((layout) => {
      const json = JSON.stringify(layout);
      if (json === previous) return 0;
      previous = json;
      return layout;
    });
    return { h: combo.hyphens, j: combo.justify, p: combo.pretty, l: layouts };
  });
  animations[name] = {
    browser,
    row: frames.length,
    words,
    separators,
    widths: [widths[0], widths[widths.length - 1]],
    combos,
  };
  for (const c of strip(words.join(" "))) textChars.add(c);
  for (const c of browser) captionChars.add(c);
  if (size && (size[0] !== width || size[1] !== height))
    throw new Error("animations of different sizes");
  size = [width, height];

  // First frame: the first combination at the narrowest width
  const first = data.combos[0].layouts[0];
  const y = (line) => (pad + label + line * lineHeight + baseline).toFixed(2);
  const texts = words.flatMap((word, i) => {
    const p = first[i];
    if (p.length === 3)
      return [
        `<text class="lf1-text" x="${pad + p[1] / 10}" y="${y(p[0])}">${escape(strip(word))}</text>`,
      ];
    return [
      `<text class="lf1-text" x="${pad + p[1] / 10}" y="${y(p[0])}">${escape(strip(word.slice(0, p[3])))}-</text>`,
      `<text class="lf1-text" x="${pad + p[5] / 10}" y="${y(p[4])}">${escape(strip(word.slice(p[3])))}</text>`,
    ];
  });
  const top = frames.length * height;
  views.push(`<view id="${name}" viewBox="0 ${top} ${width} ${height}"/>`);
  frames.push(`<g transform="translate(0 ${top})">
<rect width="${width}" height="${height}" class="lf1-background"/>
<text class="lf1-caption" x="${pad}" y="${pad + 16}">${escape(browser)} · ${widths[0]}px</text>
${texts.join("\n")}
<rect x="${pad + widths[0]}" y="${pad + label - 6}" width="1" height="${lines * lineHeight + 12}" class="lf1-edge"/>
</g>`);
}

const payload = JSON.stringify(animations).replace(/</g, "\\u003c");
const [width, height] = size;
const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
<style>
svg { font-variant-ligatures: none; }
.lf1-background { fill: #fff9f0; }
.lf1-text { font-family: serif; font-size: 20px; fill: #000; }
.lf1-caption { font-family: sans-serif; font-size: 15px; fill: #404040; }
.lf1-on { fill: #21519c; }
.lf1-off { fill: #b0b0b0; text-decoration: line-through; }
.lf1-edge { fill: #b80f28; opacity: 0.5; }
.lf1-shy { fill: #d00; }
.lf1-nbsp { fill: #80c; }
.lf1-hidden { visibility: hidden; }
</style>
${views.join("\n")}
${frames.join("\n")}
<text class="lf1-text lf1-hidden">${escape([...textChars].join(""))}</text>
<text class="lf1-caption lf1-hidden">${escape([...captionChars].join(""))}</text>
<script type="application/json" id="data">${payload}</script>
<script><![CDATA[
${player}]]></script>
</svg>
`;
const target = new URL("content/media/images/line-break.svg", ROOT);
fs.writeFileSync(target, svg);
console.log(`${target.pathname}: ${svg.length} bytes`);
