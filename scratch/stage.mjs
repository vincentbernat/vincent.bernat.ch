// Puts one segment on the stage and gives the recorder a handle on it.
//
//   stage.html?segment=042
//
// Time is the interesting part. The widget animates from requestAnimationFrame
// and performance.now(), so replacing both with a clock we turn by hand makes
// every frame reproducible and unhooks the render from wall clock time. The
// clock only takes over once the widget has loaded, so the WebAssembly setup
// still runs on real time and cannot stall.

const params = new URLSearchParams(location.search);

// -- the clock -------------------------------------------------------

// The opening demo chooses which cable is kicked out at random, so every page
// load tells a different story. A segment that carries on from the one before
// it does so by replaying the simulation from zero and fast-forwarding, which
// only lands in the same place if the sequence is the same every time. Seeded
// here, so it is.
const SEED = 0x5eed1e;
let randomState = SEED;
Math.random = () => {
  randomState |= 0;
  randomState = (randomState + 0x6d2b79f5) | 0;
  let t = Math.imul(randomState ^ (randomState >>> 15), 1 | randomState);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

const realNow = performance.now.bind(performance);
const realDateNow = Date.now;
const realRaf = window.requestAnimationFrame.bind(window);
const realCancelRaf = window.cancelAnimationFrame.bind(window);
const realSetTimeout = window.setTimeout.bind(window);
const realClearTimeout = window.clearTimeout.bind(window);

const clock = {
  virtual: false,
  now: 0,
  base: realDateNow(),
  frame: [],
  timers: new Map(),
  nextId: 1,
};

performance.now = () => (clock.virtual ? clock.now : realNow());
Date.now = () =>
  clock.virtual ? Math.round(clock.base + clock.now) : realDateNow();

window.requestAnimationFrame = (fn) => {
  if (!clock.virtual) return realRaf(fn);
  const id = clock.nextId++;
  clock.frame.push({ id, fn });
  return id;
};

window.cancelAnimationFrame = (id) => {
  if (!clock.virtual) return realCancelRaf(id);
  clock.frame = clock.frame.filter((f) => f.id !== id);
};

window.setTimeout = (fn, ms = 0, ...args) => {
  if (!clock.virtual) return realSetTimeout(fn, ms, ...args);
  const id = clock.nextId++;
  clock.timers.set(id, { at: clock.now + ms, fn, args });
  return id;
};

window.clearTimeout = (id) => {
  if (!clock.virtual) return realClearTimeout(id);
  clock.timers.delete(id);
};

// Move the clock on by one frame and let everything waiting on it run.
function advance(ms) {
  clock.now += ms;

  // Timers first: a timer may queue a frame callback.
  const due = [...clock.timers.entries()]
    .filter(([, t]) => t.at <= clock.now)
    .sort((a, b) => a[1].at - b[1].at);
  for (const [id, timer] of due) {
    clock.timers.delete(id);
    try {
      timer.fn(...timer.args);
    } catch (err) {
      console.error("stage: timer failed", err);
    }
  }

  const frame = clock.frame;
  clock.frame = [];
  for (const entry of frame) {
    try {
      entry.fn(clock.now);
    } catch (err) {
      console.error("stage: frame failed", err);
    }
  }

  // CSS animations and transitions run off their own clock, so walk them
  // forward by hand to keep them in step with the diagram.
  //
  // One that has run past its end has to be finished rather than left paused
  // there. The widget cleans up after itself in animationend handlers — the
  // slide between two states removes its ghost copy of the diagram that way —
  // and a paused animation never fires one, so the ghost would stay on screen
  // over the real diagram for the rest of the segment.
  for (const animation of document.getAnimations()) {
    try {
      animation.pause();
      const at = Number(animation.currentTime ?? 0) + ms;
      animation.currentTime = at;
      const end = animation.effect?.getComputedTiming?.().endTime;
      // Anything endless, like the waiting hourglass, keeps running.
      if (typeof end === "number" && Number.isFinite(end) && at >= end)
        animation.finish();
    } catch {
      // A finished animation refuses a new time. Nothing to do about it.
    }
  }
}

// -- rendering a segment ---------------------------------------------

const slot = document.getElementById("slot");
const chapter = document.getElementById("chapter");
const credit = document.getElementById("credit");

const el = (tag, props = {}, ...children) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children.filter(Boolean));
  return node;
};

function renderTitle(segment) {
  const { level, title } = segment.visual;
  const box = el("div", { className: "stage-title" });
  box.append(el(level === 1 ? "h1" : "h2", { textContent: title }));
  if (level === 1) box.append(el("div", { className: "rule" }));
  return box;
}

function renderTopology(segment, data) {
  const topology = data.topologies[segment.visual.topology];
  const wrap = el("div", { className: "stage-topology" });
  if (!topology) return wrap;
  const host = el("div", { className: "mstp-topology" });
  const pre = el("pre");
  pre.append(el("code", { textContent: topology.source }));
  host.append(pre);
  wrap.append(host);
  return wrap;
}

async function renderCode(segment) {
  const wrap = el("div", { className: "stage-code" });
  const response = await fetch(`/out/blocks/${segment.slug}.html`);
  wrap.innerHTML = await response.text();
  return wrap;
}

// Code blocks vary from six lines to nearly thirty, and the console output has
// lines wider than the frame. Rather than clip either way, shrink the type
// until the whole block fits.
function fitCode() {
  const block = slot.querySelector(".stage-code");
  const pre = block?.querySelector("pre");
  if (!pre) return;
  const room = slot.getBoundingClientRect();
  for (let size = 1.35; size >= 0.6; size -= 0.025) {
    pre.style.fontSize = `${size}rem`;
    const box = block.getBoundingClientRect();
    if (
      pre.scrollWidth <= pre.clientWidth + 1 &&
      box.height <= room.height &&
      box.width <= room.width
    )
      return;
  }
}

function renderImage(segment) {
  const figure = el("figure", { className: "stage-image" });
  figure.style.margin = "0";
  const src = segment.visual.src.replace(/^images\//, "/media/images/");
  figure.append(el("img", { src, alt: segment.visual.alt }));
  return figure;
}

function renderNote(segment) {
  return el("div", { className: "stage-note", textContent: segment.text });
}

function renderPoem(segment) {
  const box = el("div", { className: "stage-poem" });
  box.append(
    el("img", { src: `/${segment.visual.photo}`, alt: "Radia Perlman" }),
  );
  const lines = el("div", { className: "lines" });
  // Lit by default: without timings yet, a fully greyed-out poem looks broken
  // rather than unfinished.
  for (const line of segment.visual.lines)
    lines.append(el("p", { textContent: line, className: "on" }));
  lines.append(
    el("div", {
      className: "attribution",
      textContent: segment.visual.attribution,
    }),
  );
  box.append(lines);
  return box;
}

// -- the widget -------------------------------------------------------

// mount() loads MSTPD before the widget can do anything, so wait for the core
// to turn up rather than for a fixed delay.
function widgetOf() {
  const host = slot.querySelector(".mstp-host");
  return host && window.__mstp?.widgets.get(host);
}

async function waitForWidget(timeout = 30000) {
  const deadline = realNow() + timeout;
  for (;;) {
    const w = widgetOf();
    // The core has to be up and the diagram drawn at least once: the viewBox
    // is what tells us the shape to fit the stage to. A demo also has to have
    // started — its loop is kicked off by an IntersectionObserver, and until
    // that has fired there is no frame callback for the clock to drive, so a
    // fast-forward would silently do nothing.
    if (w?.mstp && w.svg?.viewBox?.baseVal?.width > 0) return w;
    if (realNow() > deadline)
      throw new Error(w ? "widget drew nothing" : "widget never became ready");
    await new Promise((r) => realSetTimeout(r, 25));
  }
}

// The widget keeps seek() to itself, but it listens for clicks on control links
// anywhere in the page, and picks the closest topology before the link. So an
// anchor placed just after the host drives it, exactly as the article does.
function fireCue(spec) {
  const host = slot.querySelector(".mstp-host");
  if (!host) throw new Error("no widget to drive");
  const anchor = el("a", { href: `#mstp:${spec}` });
  anchor.style.display = "none";
  host.after(anchor);
  anchor.click();
  anchor.remove();
}

// The widget builds its shadow styles from the page's own copy of
// 2026-spanning-tree.css, and the shadow root is open, so a second sheet
// adopted after it can trim the parts that only make sense to a reader: the
// buttons nobody clicks in a video, and the side panel that costs a third of
// the width. The clock stays, it tells the viewer where the simulation is.
const VIDEO_OVERRIDES = `
  .mstp-topo .mstp-btn,
  .mstp-topo .mstp-slow,
  .mstp-topo .mstp-detach {
    display: none !important;
  }
  .mstp-topo .mstp-bar {
    background: transparent;
    border-bottom: 0;
    padding-bottom: 0;
  }
  .mstp-topo .mstp-clock {
    font-size: 1.15em;
  }
  /* A narrow widget drops the convergence time onto a second line. That is the
     right call on a page, but here it makes the bar taller the moment the
     hourglass appears and the diagram jumps. Keep it on one line: there is
     always room, since the bar has no buttons on it. */
  .mstp-topo .mstp-clock-c {
    display: inline !important;
  }
  .mstp-topo .mstp-clock-c:not(:empty)::before {
    content: "·" !important;
    margin: 0 0.2em;
  }
  .mstp-topo.mstp-hide-panel .mstp-panel {
    display: none !important;
  }
  .mstp-topo .mstp-legend {
    font-size: 0.95em;
  }
  /* Purely decorative CSS animations. Under a clock we turn by hand the
     browser never runs a rendering tick, so these never play and never end —
     they just sit frozen on their first keyframe, which for the clock bump
     means a green highlight stuck behind the numbers. */
  .mstp-topo .mstp-bump,
  .mstp-topo .mstp-wait {
    animation: none !important;
    background: transparent !important;
    box-shadow: none !important;
  }
  /* On a page the widget keeps itself under half the viewport so it never
     takes over the article. The stage is the opposite: the diagram is all
     there is, and it should use the frame. */
  .mstp-topo {
    max-height: none;
  }
  /* The stage is flex: 0 1 auto, so it shrinks but never grows. On a page that
     is right, the diagram sets the height. Here the height is given and the
     diagram has to take it. */
  .mstp-topo .mstp-stage {
    flex: 1 1 auto;
  }
`;

let overrideSheet = null;

function applyOverrides(showPanel) {
  const host = slot.querySelector(".mstp-host");
  const shadow = host?.shadowRoot;
  if (!shadow) return;
  if (!overrideSheet) {
    overrideSheet = new CSSStyleSheet();
    overrideSheet.replaceSync(VIDEO_OVERRIDES);
  }
  if (!shadow.adoptedStyleSheets.includes(overrideSheet))
    shadow.adoptedStyleSheets = [...shadow.adoptedStyleSheets, overrideSheet];
  shadow
    .querySelector(".mstp-topo")
    ?.classList.toggle("mstp-hide-panel", !showPanel);
}

// Fitting a diagram to the stage.
//
// The widget is built for an article, where the width is given and the height
// follows. Here it is the other way round: the frame is 16:9 and the height is
// the scarce part. Two things get in the way. The SVG is a stretched flex item,
// so the aspect-ratio the widget puts on it never decides its height; and
// layout() derives the viewBox from whatever box the SVG ends up with, then
// pulls the grid to fill it, up to a limit, leaving the rest as empty margin.
//
// So: read the grid's own aspect off svg.style.aspectRatio, give the canvas an
// explicit height, and set the host width to match. The ResizeObserver the
// widget puts on the SVG then re-runs the layout by itself, and the viewBox
// comes out at the grid's own shape with nothing left over.
function fitTopology() {
  const host = slot.querySelector(".mstp-host");
  const w = widgetOf();
  if (!host || !w?.svg || !w?.canvas) return;
  const [gridW, gridH] = (w.svg.style.aspectRatio || "").split("/").map(Number);
  if (!gridW || !gridH) return;
  const aspect = gridW / gridH;

  const room = slot.getBoundingClientRect();
  // Everything the widget draws outside the diagram: the clock bar, the legend
  // and the two borders. Measured on those parts rather than as the difference
  // between the host and the canvas, which would feed the height we are about
  // to set back into the next call.
  const shadow = host.shadowRoot;
  const chrome =
    (shadow?.querySelector(".mstp-bar")?.offsetHeight ?? 0) +
    (shadow?.querySelector(".mstp-legend")?.offsetHeight ?? 0) +
    2;

  let height = room.height - chrome;
  let width = height * aspect;
  if (width > room.width) {
    width = room.width;
    height = width / aspect;
  }
  // Give the host a definite height as well: .mstp-topo is a column flex box
  // whose stage is allowed to shrink, so without one the canvas is squeezed and
  // the diagram spills over the legend.
  host.style.width = `${Math.floor(width)}px`;
  host.style.height = `${Math.ceil(height + chrome)}px`;
  // A percentage height does not resolve through the shadow boundary here, so
  // the widget root gets the same pixel height as the element hosting it.
  w.root.style.height = `${Math.ceil(height + chrome)}px`;
  w.canvas.style.height = "";
}

// True once the diagram has stopped moving.
//
// The one honest signal is the frame loop: the widget cancels it when a step
// finishes. w.wave and w.flights are not it, they keep holding the last wave
// and its pills after everything has come to rest.
function idle() {
  const w = widgetOf();
  if (!w) return true;
  return !w.raf;
}

// -- boot --------------------------------------------------------------

async function main() {
  const data = await (await fetch("/out/segments.json")).json();
  const wanted = params.get("segment");
  const segment =
    data.segments.find((s) => s.id === wanted || s.slug === wanted) ??
    data.segments[0];

  chapter.textContent = segment.section ?? "";
  credit.textContent = segment.credit ?? "";
  document.title = `${segment.id} ${segment.slug}`;

  let node;
  switch (segment.visual.type) {
    case "title":
      node = renderTitle(segment);
      break;
    case "topology":
      node = renderTopology(segment, data);
      break;
    case "packet":
    case "code":
      node = await renderCode(segment);
      break;
    case "image":
      node = renderImage(segment);
      break;
    case "poem":
      node = renderPoem(segment);
      break;
    default:
      node = renderNote(segment);
  }
  slot.append(node);

  let widget = null;
  if (segment.visual.type === "packet" || segment.visual.type === "code")
    fitCode();
  if (segment.visual.type === "topology") {
    window.__mstp.mountAll(slot);
    widget = await waitForWidget();
    applyOverrides(segment.visual.panel === true);
    fitTopology();
    fitTopology(); // the legend may have rewrapped at the new width
  }

  await document.fonts.ready;
  document.getElementById("stage").hidden = false;

  window.__stage = {
    segment,
    data,
    advance,
    fireCue,
    idle,
    // One round trip per frame instead of two: move the clock on and say
    // whether the diagram has come to rest.
    tick: (ms) => {
      advance(ms);
      return idle();
    },
    // Run the clock on without capturing, to reach the point a simulation has
    // already got to in the segment before this one.
    spin: (ms, step) => {
      for (let spent = 0; spent < ms; spent += step) advance(step);
    },
    // Run the clock on until nothing is moving, to reach the state a control
    // link settles at. Returns how long that took.
    settle: (ms, limit = 30000) => {
      let spent = 0;
      while (spent < limit) {
        advance(ms);
        spent += ms;
        if (idle()) break;
      }
      return spent;
    },
    freeze: async () => {
      clock.virtual = true;
      clock.now = realNow();
      // Whatever is animating is waiting on a real frame callback taken out
      // before the switch. Until that fires and asks for the next one — which
      // now comes here — the queue is empty and turning the clock does nothing
      // at all. Wait for the handover rather than race it.
      const deadline = realNow() + 3000;
      while (!clock.frame.length && realNow() < deadline)
        await new Promise((resolve) => realSetTimeout(resolve, 8));
      return clock.frame.length > 0;
    },
    thaw: () => {
      clock.virtual = false;
    },
    // The poem highlights a line at a time as she reads.
    poemLine: (index) => {
      const lines = [...slot.querySelectorAll(".lines p")];
      lines.forEach((p, i) =>
        p.classList.toggle("on", index === null || i === index),
      );
    },
    state: () => {
      const w = widgetOf();
      return w
        ? {
            clock: w.clock,
            flights: w.flights?.length ?? 0,
            running: Boolean(w.raf),
            wave: Boolean(w.wave),
          }
        : null;
    },
    fit: fitTopology,
    hasWidget: Boolean(widget),
  };
  window.dispatchEvent(new Event("stage:ready"));
}

main().catch((err) => {
  console.error(err);
  window.__stageError = String(err);
});
