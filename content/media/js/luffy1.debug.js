/* Debug tools. Each key is the letter typed after ←, ←. */

let gridState = 0;

// Characters added by ssg/html/typography.py, with the class to show them
const spaces = {
  "­": "lf-debug-shy",
  "​": "lf-debug-zwsp",
  " ": "lf-debug-nbsp",
  " ": "lf-debug-nnbsp",
};
const spacesRe = new RegExp(`[${Object.keys(spaces).join("")}]`, "g");
let spacesLayer = null;

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

const drawSpaces = () => {
  // Marks go in a layer above the text, as changing the text changes the
  // layout
  spacesLayer?.remove();
  spacesLayer = document.createElement("div");
  spacesLayer.className = "lf-debug-spaces";
  const range = document.createRange();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node; (node = walker.nextNode());) {
    if (node.parentElement.closest("script, style")) continue;
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
    if (spacesLayer) {
      spacesLayer.remove();
      spacesLayer = null;
      removeEventListener("resize", drawSpaces);
    } else {
      drawSpaces();
      addEventListener("resize", drawSpaces);
    }
  },
};
