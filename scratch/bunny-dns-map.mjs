// Generate content/media/images/bunny-dns-map.svg.
//
// Usage: node scratch/bunny-dns-map.mjs land-50m.json
//
// land-50m.json comes from the world-atlas npm package.
//
// The land is transparent: 2026-bunny-geodns.js paints it from a canvas under the image.
// Provider icons are outside of the map. Each one has a view, like
// #hetzner, that 2026-bunny-geodns.js uses to place the servers.
// Keep the projection constants and the areas of the ship, the whale and
// the shark in sync with 2026-bunny-geodns.js.

import { readFileSync, writeFileSync } from "node:fs";

const topo = JSON.parse(readFileSync(process.argv[2], "utf8"));

const W = 1000;
const LAT_TOP = 75;
const LAT_BOTTOM = -57;
const RAD = Math.PI / 180;
const miller = (phi) => 1.25 * Math.log(Math.tan(Math.PI / 4 + 0.4 * phi));
const K = W / (2 * Math.PI);
const Y0 = K * miller(LAT_TOP * RAD);
const H = Math.round(Y0 - K * miller(LAT_BOTTOM * RAD));
const project = (lon, lat) => [
  W / 2 + K * lon * RAD,
  Y0 - K * miller(Math.max(-89, Math.min(89, lat)) * RAD),
];

// Decode TopoJSON arcs into longitude/latitude points
const [sx, sy] = topo.transform.scale;
const [tx, ty] = topo.transform.translate;
const arcs = topo.arcs.map((arc) => {
  let x = 0,
    y = 0;
  return arc.map(([dx, dy]) => {
    x += dx;
    y += dy;
    return [x * sx + tx, y * sy + ty];
  });
});
const ring = (indexes) =>
  indexes.flatMap((i, n) => {
    const points = i < 0 ? arcs[~i].slice().reverse() : arcs[i];
    return n ? points.slice(1) : points;
  });

// Make longitudes continuous along a ring, then project it once more on each
// side of the antimeridian when it crosses it. Rings around a pole are
// dropped.
function unwrap(points) {
  let shift = 0;
  const out = points.map(([lon, lat], i) => {
    if (i) {
      const prev = points[i - 1][0];
      if (lon - prev > 180) shift -= 360;
      else if (prev - lon > 180) shift += 360;
    }
    return [lon + shift, lat];
  });
  if (shift) return [];
  const lons = out.map(([lon]) => lon);
  const copies = [0];
  if (Math.min(...lons) < -180) copies.push(360);
  if (Math.max(...lons) > 180) copies.push(-360);
  return copies.map((offset) =>
    out.map(([lon, lat]) => project(lon + offset, lat)),
  );
}

// Douglas-Peucker simplification
function simplify(points, tolerance) {
  const keep = new Uint8Array(points.length);
  keep[0] = keep[points.length - 1] = 1;
  const stack = [[0, points.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    const [ax, ay] = points[a];
    const [bx, by] = points[b];
    const len = Math.hypot(bx - ax, by - ay);
    let max = 0,
      index = -1;
    for (let i = a + 1; i < b; i++) {
      const [px, py] = points[i];
      const d = len
        ? Math.abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / len
        : Math.hypot(px - ax, py - ay);
      if (d > max) {
        max = d;
        index = i;
      }
    }
    if (max > tolerance) {
      keep[index] = 1;
      stack.push([a, index], [index, b]);
    }
  }
  return points.filter((_, i) => keep[i]);
}

const area = (points) =>
  Math.abs(
    points.reduce((sum, [x, y], i) => {
      const [nx, ny] = points[(i + 1) % points.length];
      return sum + x * ny - nx * y;
    }, 0) / 2,
  );

const polygons = topo.objects.land.geometries.flatMap((g) =>
  g.type === "Polygon" ? [g.arcs] : g.arcs,
);
const landPath = polygons
  .flatMap((polygon) => polygon.flatMap((r) => unwrap(ring(r))))
  .filter((points) => points.some(([, y]) => y > -2 && y < H + 2))
  .map((points) => simplify(points, 0.25))
  .filter((points) => points.length > 3 && area(points) > 0.8)
  .map((points) => {
    let px = 0,
      py = 0;
    return (
      points
        .map(([x, y], i) => {
          const rx = Math.round(x * 10),
            ry = Math.round(y * 10);
          const out = i
            ? `l${(rx - px) / 10},${(ry - py) / 10}`
            : `M${rx / 10},${ry / 10}`;
          px = rx;
          py = ry;
          return out;
        })
        .filter((cmd) => cmd !== "l0,0")
        .join("") + "Z"
    );
  })
  .join("")
  .replace(/([,l])0\./g, "$1.")
  .replace(/([,l])-0\./g, "$1-.");
const at = (lat, lon) => project(lon, lat).map((v) => +v.toFixed(1));

// Provider icons, each one in the middle of a square view
const ICON_BOX = 22;
const ICONS = {
  sapinet: { w: 9, h: 17 },
  hetzner: { w: 14, h: 14 },
  vultr: { w: 17, h: 15 },
};
const icons = Object.entries(ICONS)
  .map(([name, { w, h }], k) => {
    const x = W + 10 + k * (ICON_BOX + 10);
    return `<g class="icon"><use href="#${name}-logo" x="${x + (ICON_BOX - w) / 2}" y="${(ICON_BOX - h) / 2}" width="${w}" height="${h}"/></g>
<view id="${name}" viewBox="${x} 0 ${ICON_BOX} ${ICON_BOX}"/>`;
  })
  .join("\n");

// A cloud is a set of circles: [cx, cy, r]
function cloud(x, y, scale, circles) {
  const c = circles
    .map(([cx, cy, r]) => `<circle cx="${cx}" cy="${cy}" r="${r}"/>`)
    .join("");
  return `<g class="cloud" transform="translate(${x},${y}) scale(${scale})"><g class="cloud-shadow" transform="translate(6,9)">${c}</g><g class="cloud-line">${c}</g><g class="cloud-fill">${c}</g></g>`;
}
const PUFFY = [
  [0, 0, 14],
  [16, -8, 17],
  [36, -4, 15],
  [50, 4, 11],
  [26, 6, 13],
  [-12, 6, 9],
  [8, 9, 11],
  [40, 9, 9],
];
const LONG = [
  [0, 0, 10],
  [14, -7, 13],
  [31, -9, 14],
  [48, -4, 12],
  [62, 3, 9],
  [22, 4, 11],
  [42, 5, 10],
  [-10, 5, 7],
];

// Compass rose
function compass(x, y, r) {
  const points = [];
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4 - Math.PI / 2;
    const len = i % 2 ? r * 0.55 : r;
    const tip = [Math.cos(a) * len, Math.sin(a) * len];
    const side = r * (i % 2 ? 0.1 : 0.16);
    const left = [
      Math.cos(a - Math.PI / 2) * side,
      Math.sin(a - Math.PI / 2) * side,
    ];
    const right = [-left[0], -left[1]];
    const f = (p) => p.map((v) => v.toFixed(1)).join(",");
    points.push(
      `<path class="rose-dark" d="M0,0L${f(left)}L${f(tip)}Z"/>`,
      `<path class="rose-light" d="M0,0L${f(right)}L${f(tip)}Z"/>`,
    );
  }
  return `<g class="compass" transform="translate(${x},${y})">
  <circle class="rose-ring" r="${r * 0.72}"/>
  <circle class="rose-ring" r="${r * 0.62}"/>
  ${points.reverse().join("\n  ")}
  <circle class="rose-dark" r="2"/>
  <text y="${-r - 4}" text-anchor="middle">N</text>
</g>`;
}

// The ship artwork is about 2740x2290 units, with the bottom of the hull at
// 2960. It floats: the part under the waterline is faded.
const SHIP_SCALE = 0.021;
const shipWaterline = `M-36,6${"q5,-3 10,0t10,0".repeat(4)}`;
const shipArt = `<g transform="translate(0,6) scale(${SHIP_SCALE}) translate(-3456,-2850) matrix(13.333333,0,0,-13.333333,0,3636)">${readFileSync(
  new URL("bunny-dns-map-ship.svg", import.meta.url),
  "utf8",
).replace(/<!--.*?-->\n/s, "")}</g>`;
const ship = (x, y) => `<g class="ship" transform="translate(${x},${y})">
  <path class="ship-wake" d="M-46,9q6,-3 12,0t12,0M-42,15q5,-3 10,0t10,0"/>
  <g clip-path="url(#ship-under)" opacity="0.35"><use class="ship-bob" href="#ship-art"/></g>
  <g clip-path="url(#ship-over)"><use class="ship-bob" href="#ship-art"/></g>
  <path class="ship-wave" d="${shipWaterline}"/>
</g>`;

// The whale artwork is about 830x440 units. It swims at the surface: the
// part under the waterline is faded.
const WHALE_SCALE = 0.075;
const WATERLINE = 480;
const waterline = `M0,${WATERLINE}${"q30,-16 60,0t60,0".repeat(8)}`;
const whaleArt = readFileSync(
  new URL("bunny-dns-map-whale.svg", import.meta.url),
  "utf8",
).replace(/<!--.*?-->\n/s, "");
const whale = (
  x,
  y,
) => `<g class="whale" transform="translate(${x},${y}) scale(${WHALE_SCALE}) translate(-450,${-WATERLINE})">
  <g clip-path="url(#whale-under)" opacity="0.35"><use class="whale-bob" href="#whale-art"/></g>
  <g clip-path="url(#whale-over)"><use class="whale-bob" href="#whale-art"/></g>
  <path class="whale-wave" d="${waterline}"/>
  <path class="whale-wave" d="M-60,${WATERLINE + 60}q40,-20 80,0t80,0M760,${WATERLINE - 40}q40,-20 80,0t80,0"/>
</g>`;

// Two fins break the surface, their lower part fades out.
const sharkWaterline = `M-40,0${"q5,-3 10,0t10,0".repeat(5)}`;
const sharkArt = `<path class="shark-fin" d="M-6,0C-2,-9 4,-17 13,-21C10,-12 10,-5 15,0L16,9H-9Z"/>
  <path class="shark-fin" d="M-34,0C-32,-5 -29,-8 -25,-10C-26,-6 -26,-3 -23,0L-22,9H-36Z"/>`;
const shark = (x, y) => `<g class="shark" transform="translate(${x},${y})">
  <g clip-path="url(#shark-under)" mask="url(#shark-fade)" opacity="0.5"><use class="shark-swim" href="#shark-art"/></g>
  <g clip-path="url(#shark-over)"><use class="shark-swim" href="#shark-art"/></g>
  <path class="shark-wave" d="${sharkWaterline}M-20,8q5,-3 10,0t10,0t10,0"/>
</g>`;

// Animals with the box around them and their moves
const SPRITES = [
  { lat: -28, lon: -18, box: [-56, -48, 92, 70], draw: ship },
  { lat: -32, lon: 78, box: [-44, -28, 108, 42], draw: shark },
  { lat: 10, lon: -132, box: [-44, -30, 88, 46], draw: whale },
];
const sprites = SPRITES.map(({ lat, lon, draw }) => draw(...at(lat, lon))).join(
  "\n",
);
const patches = SPRITES.map(({ lat, lon, box }) => {
  const [x, y] = at(lat, lon);
  const [left, top, width, height] = box;
  const rect = `x="${+(x + left).toFixed(1)}" y="${+(y + top).toFixed(1)}" width="${width}" height="${height}"`;
  return `<rect class="sea" ${rect}/><rect class="waves" ${rect}/>`;
}).join("\n");

// Ease-in-out as a staircase with a step for each frame: the browser only
// redraws when a value changes. The moves are slow, a step is less than a
// pixel.
const staircase = (duration, fps) => {
  const n = Math.round(duration * fps);
  // cubic-bezier(0.42, 0, 0.58, 1)
  const bezier = (t, a, b) =>
    3 * a * t * (1 - t) ** 2 + 3 * b * t ** 2 * (1 - t) + t ** 3;
  const ease = (x) => {
    let lo = 0;
    let hi = 1;
    for (let i = 0; i < 30; i++) {
      const mid = (lo + hi) / 2;
      if (bezier(mid, 0.42, 0.58) < x) lo = mid;
      else hi = mid;
    }
    return bezier((lo + hi) / 2, 0, 1);
  };
  const f = (v, digits) => +v.toFixed(digits);
  const points = [];
  for (let i = 0; i < n; i++) {
    points.push(
      `${f(ease(i / n), 3)} ${f((i / n) * 100, 2)}% ${f(((i + 1) / n) * 100, 2)}%`,
    );
  }
  return `linear(${points.join(", ")}, 1)`;
};

const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<style>
.sea { fill: #8fd0dc; }
.shallow { fill: none; stroke: #c3e9ee; stroke-width: 14; stroke-linejoin: round; }
.ring { fill: none; stroke: #6fb3c4; stroke-width: 22; stroke-dasharray: 2 5; stroke-linejoin: round; }
.coast { fill: none; stroke: #4b3621; stroke-width: 2.4; stroke-linejoin: round; }
.waves { fill: url(#waves); }
.wave { fill: none; stroke: #3f8ea3; stroke-width: 1.1; stroke-linecap: round; }
.frame { fill: none; stroke: #4b3621; stroke-width: 3; }
.cloud-line circle { fill: none; stroke: #4b3621; stroke-width: 3; }
.cloud-shadow circle { fill: #1d4f5c; fill-opacity: 0.25; }
.cloud-fill circle { fill: #fdfdf8; }
/* The page inverts images in dark mode. These colors become night clouds. */
@media (prefers-color-scheme: dark) {
  .cloud-line circle { stroke: #d9dfef; }
  .cloud-shadow circle { fill: #e7f2fc; }
  .cloud-fill circle { fill: #939fb7; }
}
.rose-dark { fill: #4b3621; }
.rose-light { fill: #f3e6c8; stroke: #4b3621; stroke-width: 0.6; }
.rose-ring { fill: none; stroke: #4b3621; stroke-width: 0.8; }
.compass text { font: 13px serif; fill: #4b3621; }
.whale-wave { fill: none; stroke: #fdfdf8; stroke-width: 20; stroke-linecap: round; }
.ship-wave, .ship-wake, .shark-wave { fill: none; stroke: #fdfdf8; stroke-width: 1.4; stroke-linecap: round; }
.shark-fin { fill: #5f6f7a; stroke: #2c353b; stroke-width: 1; stroke-linejoin: round; }
.icon { filter: url(#halo); }
/* 2026-bunny-geodns.js puts the #sprites view (or #sprites-dark) on top of the map, in an
   object. It only shows the animals and a patch of sea under them, which
   hides the still animals of the map. Only this view is animated: in an
   image, an animation redraws the whole image at each frame. */
.patches { display: none; }
:is(#sprites, #sprites-dark):target ~ .patches { display: inline; }
:is(#sprites, #sprites-dark):target ~ :not(.patches, .sprites) { display: none; }
/* The page inverts the map in dark mode, but not this view: 2026-bunny-geodns.js uses
   #sprites-dark instead. The animals keep their colors, the sea under them is
   inverted like the map. A media query does not work: the object uses a light
   color scheme. */
#sprites-dark:target ~ .patches { filter: url(#invert); }
/* The art moves inside a fixed waterline: the clip stays on the parent group */
@media (prefers-reduced-motion: no-preference) {
  :is(#sprites, #sprites-dark):target ~ .sprites .ship-bob { animation: ship-bob 3.5s ${staircase(3.5, 7)} infinite alternate; }
  :is(#sprites, #sprites-dark):target ~ .sprites .whale-bob { animation: whale-bob 2.75s ${staircase(2.75, 7)} infinite alternate; }
  :is(#sprites, #sprites-dark):target ~ .sprites .shark-swim { animation: shark-swim 6.5s ${staircase(6.5, 7)} infinite alternate; }
}
@keyframes ship-bob {
  from { transform: translate(0, 6px) rotate(-5deg) translate(0, -6px); }
  to { transform: translate(0, 8.5px) rotate(5deg) translate(0, -6px); }
}
@keyframes whale-bob {
  from { transform: translate(450px, ${WATERLINE}px) rotate(-3deg) translate(-450px, -${WATERLINE}px); }
  to { transform: translate(450px, ${WATERLINE + 40}px) rotate(3deg) translate(-450px, -${WATERLINE}px); }
}
/* With a translation alone, Firefox snaps the fins to whole pixels */
@keyframes shark-swim {
  from { transform: rotate(0.1deg); }
  to { transform: translate(10px, 1px) rotate(0.1deg); }
}
</style>
<defs>
  <filter id="invert" color-interpolation-filters="sRGB">
    <feComponentTransfer>
      <feFuncR type="table" tableValues="1 0"/>
      <feFuncG type="table" tableValues="1 0"/>
      <feFuncB type="table" tableValues="1 0"/>
    </feComponentTransfer>
    <feColorMatrix type="hueRotate" values="180"/>
  </filter>
  <filter id="halo" x="-30%" y="-30%" width="160%" height="160%">
    <feMorphology in="SourceAlpha" operator="dilate" radius="1.5" result="grown"/>
    <feGaussianBlur in="grown" stdDeviation="0.6" result="soft"/>
    <feFlood flood-color="#fff" flood-opacity="0.7"/>
    <feComposite operator="in" in2="soft"/>
    <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <path id="land" d="${landPath}"/>
  <g id="ship-art">${shipArt}</g>
  <clipPath id="ship-over"><path d="${shipWaterline}V-60H-36Z"/></clipPath>
  <clipPath id="ship-under"><path d="${shipWaterline}V30H-36Z"/></clipPath>
  <g id="shark-art">${sharkArt}</g>
  <clipPath id="shark-over"><path d="${sharkWaterline}V-30H-40Z"/></clipPath>
  <clipPath id="shark-under"><path d="${sharkWaterline}V30H-40Z"/></clipPath>
  <linearGradient id="fade-down" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff"/>
    <stop offset="1" stop-color="#000"/>
  </linearGradient>
  <mask id="shark-fade" maskUnits="userSpaceOnUse" x="-40" y="-30" width="100" height="40">
    <rect x="-40" y="-30" width="100" height="30" fill="#fff"/>
    <rect x="-40" y="-2" width="100" height="10" fill="url(#fade-down)"/>
  </mask>
  <g id="whale-art">${whaleArt}</g>
  <clipPath id="whale-over"><path d="${waterline}V0H0Z"/></clipPath>
  <clipPath id="whale-under"><path d="${waterline}V1000H0Z"/></clipPath>
  <mask id="sea" maskUnits="userSpaceOnUse" x="0" y="0" width="${W}" height="${H}">
    <rect width="${W}" height="${H}" fill="#fff"/>
    <use href="#land" fill="#000"/>
  </mask>
  <pattern id="waves" width="64" height="36" patternUnits="userSpaceOnUse">
    <path class="wave" d="M6,10q3,-3 6,0t6,0M38,28q3,-3 6,0t6,0"/>
  </pattern>
  <linearGradient id="gradient6" x1="124.74" y1="38.95" x2="146.12" y2="38.95" gradientTransform="matrix(1,0,0,-1,0,53.45)" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#00aab9"/>
    <stop offset=".47" stop-color="#00ba89"/>
    <stop offset="1" stop-color="#01c853"/>
  </linearGradient>
  <linearGradient id="gradient6-4" x1="129.77" y1="15.29" x2="144.5" y2="52.79" href="#gradient6"/>
  <linearGradient id="gradient6-5" x1="132.61" y1="12.49" x2="146.57" y2="43.87" href="#gradient6"/>
  <linearGradient id="gradient6-6" x1="132.45" y1="-2.35" x2="142.59" y2="32.46" href="#gradient6"/>
  <symbol id="sapinet-logo" viewBox="124.74 5.25 21.38 40.32">
    <polygon points="124.74,23.76 146.12,23.76 135.43,5.25" fill="url(#gradient6-4)"/>
    <polygon points="124.74,34.62 146.12,34.62 135.43,16.1" fill="url(#gradient6-5)"/>
    <polygon points="124.74,45.57 146.12,45.57 135.43,27.06" fill="url(#gradient6-6)"/>
    <polygon points="135.43,16.1 146.12,23.76 139.85,23.76" fill="#293c3e" opacity=".4"/>
    <polygon points="135.43,27.06 146.12,34.62 139.8,34.62" fill="#293c3e" opacity=".4"/>
  </symbol>
  <symbol id="hetzner-logo" viewBox="312.7 256.2 17 16.7">
    <path fill="#d50c2d" d="m 313.49369,272.88649 h 2.3325 c 0.525,0 0.75,-0.2175 0.75,-0.75 v -5.9025 h 9.2925 v 5.9025 c 0,0.525 0.2175,0.75 0.75,0.75 h 2.3475 c 0.5325,0 0.75,-0.2175 0.75,-0.75 v -15.1875 c 0,-0.5325 -0.2175,-0.75 -0.75,-0.75 h -2.3475 c -0.525,0 -0.75,0.21 -0.75,0.75 v 6 h -9.3 v -6 c 0,-0.525 -0.2175,-0.75 -0.75,-0.75 h -2.325 c -0.525,0 -0.75,0.21 -0.75,0.75 v 15.1875 c 0,0.525 0.2175,0.75 0.75,0.75 z"/>
  </symbol>
  <symbol id="vultr-logo" viewBox="0 0 96 83">
    <path fill="#c9f4ff" d="M 33.45,2.24 A 4.78,4.78 0 0 0 29.39,0 H 4.8 A 4.8,4.8 0 0 0 0.74,7.36 l 5,8 32.71,-5.12 z"/>
    <path fill="#51b9ff" d="M 38.49,10.24 A 4.78,4.78 0 0 0 34.43,8 H 9.84 a 4.8,4.8 0 0 0 -4.06,7.36 l 7.06,11.2 32.71,-5.12 z"/>
    <path fill="#007bfc" d="M 12.84,26.56 A 4.85,4.85 0 0 1 12.1,24 4.8,4.8 0 0 1 16.9,19.2 h 24.59 a 4.78,4.78 0 0 1 4.06,2.24 l 22,34.9 a 4.8,4.8 0 0 1 0,5.12 L 55.26,81 a 4.8,4.8 0 0 1 -8.12,0 z"/>
    <path fill="#007bfc" d="M 74.85,37 A 4.8,4.8 0 0 0 83,37 l 4.2,-6.7 8.06,-12.79 a 4.8,4.8 0 0 0 0,-5.12 L 88.86,2.24 A 4.78,4.78 0 0 0 84.8,0 H 60.21 a 4.8,4.8 0 0 0 -4.06,7.36 z"/>
  </symbol>
</defs>
<view id="sprites" viewBox="0 0 ${W} ${H}"/>
<view id="sprites-dark" viewBox="0 0 ${W} ${H}"/>
<g mask="url(#sea)">
  <rect class="sea" width="${W}" height="${H}"/>
  <use class="ring" href="#land"/>
  <use class="shallow" href="#land"/>
  <rect class="waves" width="${W}" height="${H}"/>
  <use class="coast" href="#land"/>
</g>
<g class="patches">
${patches}
</g>
<g class="sprites">
${sprites}
</g>
${compass(...at(-38, -128), 30)}
${cloud(...at(54, -165), 0.9, PUFFY)}
${cloud(...at(-50, 108), 0.8, LONG)}
${cloud(...at(-48, -40), 0.6, PUFFY)}
<rect class="frame" x="1.5" y="1.5" width="${W - 3}" height="${H - 3}"/>
${icons}
</svg>
`;

writeFileSync("content/media/images/bunny-dns-map.svg", svg);
console.log(`W=${W} H=${H} LAT_TOP=${LAT_TOP} LAT_BOTTOM=${LAT_BOTTOM}`);
