/* Debug tools. Each key is the letter typed after ←, ←. */

let gridState = 0;

const SHY = "\u00AD"; // SOFT HYPHEN
const ZWSP = "\u200B"; // ZERO WIDTH SPACE
const NBSP = "\u00A0"; // NO-BREAK SPACE
const NNBSP = "\u202F"; // NARROW NO-BREAK SPACE

// Characters added by ssg/html/typography.py, with the class to show them
const spaces = {
  [SHY]: "lf-debug-shy",
  [ZWSP]: "lf-debug-zwsp",
  [NBSP]: "lf-debug-nbsp",
  [NNBSP]: "lf-debug-nnbsp",
};
const spacesRe = new RegExp(`[${Object.keys(spaces).join("")}]`, "g");
let spacesShown = false;
let spacesLayer = null;
let spacesObserver = null;

// Lines of left-aligned text in these blocks show their rag. A rag of this
// part of the block width is red.
const ragBlocks = "p, li, dt, dd";
const ragMax = 0.15;

// Gaps between words of justified text wider than wideMin times the natural
// width of the space are shown. At wideMax times, they are red.
const wideMin = 2;
const wideMax = 4;
const wideSpaces = ` \t\n${NBSP}${NNBSP}`;
const invisible = SHY + ZWSP;

// Font descent, to find the baseline at the bottom of a text box, and natural
// width of spaces
const metrics = {};
const fontMetrics = (style) => {
  const font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  if (!(font in metrics)) {
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = font;
    metrics[font] = {
      descent: ctx.measureText("x").fontBoundingBoxDescent || 0,
      space: ctx.measureText(" ").width,
      [NBSP]: ctx.measureText(NBSP).width,
      [NNBSP]: ctx.measureText(NNBSP).width,
    };
  }
  return metrics[font];
};
const descent = (style) => fontMetrics(style).descent;

// A bar of 1ex above the baseline
const drawBar = (layer, className, style, left, bottom, width, color) => {
  const mark = document.createElement("div");
  mark.className = className;
  mark.style.left = `${left + scrollX}px`;
  mark.style.top = `calc(${bottom - descent(style) + scrollY}px - 1ex)`;
  mark.style.width = `${width}px`;
  mark.style.height = "1ex";
  mark.style.fontFamily = style.fontFamily;
  mark.style.fontSize = style.fontSize;
  mark.style.backgroundColor = color;
  layer.appendChild(mark);
};

const drawRags = (layer, blocks) => {
  for (const [block, { rects }] of blocks) {
    const style = getComputedStyle(block);
    // Only for ragged-right blocks (but it would work for justify as well).
    if (!["start", "left"].includes(style.textAlign)) continue;
    // Fragments are in text order. A fragment below the current line starts
    // a new one.
    const lines = [];
    for (const r of rects) {
      if (!r.width) continue;
      const line = lines[lines.length - 1];
      if (line && (r.top + r.bottom) / 2 < line.bottom) {
        line.top = Math.min(line.top, r.top);
        line.bottom = Math.max(line.bottom, r.bottom);
        line.right = Math.max(line.right, r.right);
      } else {
        lines.push({ top: r.top, bottom: r.bottom, right: r.right });
      }
    }
    // The last line is not a rag
    lines.pop();
    const box = block.getBoundingClientRect();
    const left =
      box.left +
      parseFloat(style.borderLeftWidth) +
      parseFloat(style.paddingLeft);
    const right =
      box.right -
      parseFloat(style.borderRightWidth) -
      parseFloat(style.paddingRight);
    for (const line of lines) {
      const rag = right - line.right;
      if (rag <= 0) continue;
      const bad = Math.min(rag / ((right - left) * ragMax), 1);
      drawBar(
        layer,
        "lf-debug-rag",
        style,
        line.right,
        line.bottom,
        rag,
        `hsl(${120 * (1 - bad)} 80% 45%)`,
      );
    }
  }
};

// Gaps around spaces, from the character before to the character after, as
// a browser may give a part of the justification to the letters
const drawWide = (layer, blocks) => {
  const range = document.createRange();
  const charRect = (node, i, last) => {
    range.setStart(node, i);
    range.setEnd(node, i + 1);
    const rects = range.getClientRects();
    return rects[last ? rects.length - 1 : 0];
  };
  for (const [block, { nodes }] of blocks) {
    if (getComputedStyle(block).textAlign !== "justify") continue;
    const chars = [];
    for (const node of nodes) {
      if (node.parentElement.closest("[hidden]")) continue;
      for (let i = 0; i < node.data.length; i++) chars.push([node, i]);
    }
    const kind = (k) => {
      const c = chars[k][0].data[chars[k][1]];
      if (wideSpaces.includes(c)) return "space";
      if (invisible.includes(c)) return "invisible";
      return "visible";
    };
    for (let k = 0; k < chars.length; k++) {
      // First space of a run
      if (kind(k) !== "space" || (k > 0 && kind(k - 1) === "space")) continue;
      let before = k - 1;
      while (before >= 0 && kind(before) !== "visible") before--;
      let after = k + 1;
      while (after < chars.length && kind(after) !== "visible") after++;
      if (before < 0 || after >= chars.length) continue;
      const a = charRect(...chars[before], true);
      const b = charRect(...chars[after], false);
      // Both on the same line
      if (!a || !b || b.top >= a.bottom || a.top >= b.bottom) continue;
      const [node, i] = chars[k];
      const style = getComputedStyle(node.parentElement);
      const m = fontMetrics(style);
      const c = node.data[i];
      const natural = m[c] ?? m.space;
      const gap = b.left - a.right;
      if (gap <= wideMin * natural) continue;
      const bad = Math.min((gap / natural - wideMin) / (wideMax - wideMin), 1);
      drawBar(
        layer,
        "lf-debug-wide",
        style,
        a.right,
        Math.max(a.bottom, b.bottom),
        gap,
        `hsl(${60 * (1 - bad)} 90% 50%)`,
      );
    }
  }
};

const drawSpaces = () => {
  // Marks go in a layer above the text
  spacesLayer?.remove();
  spacesLayer = document.createElement("div");
  spacesLayer.className = "lf-debug-spaces";
  const range = document.createRange();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const blocks = new Map();
  for (let node; (node = walker.nextNode());) {
    if (node.parentElement.closest("script, style")) continue;
    const block = node.parentElement.closest(ragBlocks);
    if (block?.closest("main.lf-main")) {
      if (!blocks.has(block)) blocks.set(block, { rects: [], nodes: [] });
      blocks.get(block).nodes.push(node);
      if (node.data.trim()) {
        range.selectNodeContents(node);
        blocks.get(block).rects.push(...range.getClientRects());
      }
    }
    const style = getComputedStyle(node.parentElement);
    spacesRe.lastIndex = 0;
    for (let m; (m = spacesRe.exec(node.data));) {
      range.setStart(node, m.index);
      range.setEnd(node, m.index + 1);
      const rect = range.getClientRects()[0];
      if (!rect) continue;
      const mark = document.createElement("div");
      mark.className = spaces[m[0]];
      mark.style.left = `${rect.left + scrollX}px`;
      mark.style.top = `${rect.top + scrollY}px`;
      mark.style.width = `${rect.width}px`;
      mark.style.height = `${rect.height - descent(style)}px`;
      mark.style.fontSize = style.fontSize;
      spacesLayer.appendChild(mark);
    }
  }
  drawRags(spacesLayer, blocks);
  drawWide(spacesLayer, blocks);
  document.body.appendChild(spacesLayer);
};

luffy.debug = {
  g() {
    // Cycle debug grid (off → grid → grid on baseline → off).
    // --lf-baseline-offset is precomputed at build time in :root.
    gridState = (gridState + 1) % 3;
    const classes = document.documentElement.classList;
    classes.toggle("lf-debug-grid-1", gridState === 1);
    classes.toggle("lf-debug-grid-2", gridState === 2);
  },
  s() {
    // Show special spaces and hyphens.
    spacesShown = !spacesShown;
    if (!spacesShown) {
      spacesObserver?.disconnect();
      spacesLayer?.remove();
      spacesLayer = null;
    } else {
      spacesObserver = new ResizeObserver(drawSpaces);
      spacesObserver.observe(document.body);
    }
  },
};
