/* Debug tools. Each key is the letter typed after ←, ←. */

let gridState = 0;

// Characters added by ssg/html/typography.py, with the class to show them
const spaces = {
  "\u00AD": "lf-debug-shy",
  "\u200B": "lf-debug-zwsp",
  "\u00A0": "lf-debug-nbsp",
  "\u202F": "lf-debug-nnbsp",
};
const spacesRe = new RegExp(`[${Object.keys(spaces).join("")}]`, "g");
let spacesShown = false;
let spacesLayer = null;
let spacesObserver = null;

// Lines of left-aligned text in these blocks show their rag. A rag of this
// part of the block width is red.
const ragBlocks = "p, li, dt, dd";
const ragMax = 0.15;

// Font descent, to find the baseline at the bottom of a text box
const descents = {};
const descent = (style) => {
  const font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  if (!(font in descents)) {
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = font;
    descents[font] = ctx.measureText("x").fontBoundingBoxDescent || 0;
  }
  return descents[font];
};

const drawRags = (layer, blocks) => {
  for (const [block, rects] of blocks) {
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
      const mark = document.createElement("div");
      mark.className = "lf-debug-rag";
      mark.style.left = `${line.right + scrollX}px`;
      mark.style.top = `calc(${line.bottom - descent(style) + scrollY}px - 1ex)`;
      mark.style.width = `${rag}px`;
      mark.style.height = "1ex";
      mark.style.fontFamily = style.fontFamily;
      mark.style.fontSize = style.fontSize;
      mark.style.backgroundColor = `hsl(${120 * (1 - bad)} 80% 45%)`;
      layer.appendChild(mark);
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
    if (block?.closest("main.lf-main") && node.data.trim()) {
      if (!blocks.has(block)) blocks.set(block, []);
      range.selectNodeContents(node);
      blocks.get(block).push(...range.getClientRects());
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
