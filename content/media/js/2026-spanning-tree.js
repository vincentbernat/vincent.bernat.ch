// SPDX-License-Identifier: GPL-2.0-or-later
//
// Turn a <pre> block describing a topology into an interactive spanning-tree
// simulation, powered by the MSTPD WebAssembly core. Write your topologies
// inside <pre class="mstp-topology"> blocks, and they are replaced in place by
// a live, clickable diagram.
//
//   <link rel="stylesheet" href="topology.css" />
//   <script type="module" src="dist/mstpd.mjs"></script>
//   <script type="module" src="topology.js"></script>
//
// Grammar (one statement per line; # or // starts a comment):
//
//   NAME @X,Y [prio=N] [proto=stp|rstp|mstp|none] [icon=C]  # a bridge at grid cell X,Y
//   A -- B [cost=N] [down] [hazard=N] [A:flag ...]     # a link between two bridges
//   A -> B [cost=N] [hazard=N] [A:flag ...]            # a one-way link (A transmits, B receives)
//   # global options
//   :protocol rstp|stp|mstp|none
//   :forward-delay N
//   :max-age N
//   :max-hops N
//   :tx-hold N
//   :demo
//
// Endpoint flags: edge, no-auto-edge, network, bpdu-guard, root-guard, no-p2p
//
// proto=none turns the spanning tree off on a bridge: it sends no BPDUs, drops
// the ones it receives, and its ports have no role or state.
//
// hazard is how often the Stan goes for a cable, 1 by default. A cable with a
// hazard of 2 is picked twice as often as a plain one, and one with a hazard of
// 0 is never picked.
//
// A regular link with an #mstp: anchor puts the nearest topology above in a
// given state, e.g. <a href="#mstp:B--C,30">: see "control links" below.
//
// The MSTPD core is loaded via its own <script> tag (above), which publishes
// window.mstpd; this module picks loadMSTPD off it rather than importing. We
// could instead import it:
//
// import { loadMSTPD } from "./dist/mstpd.mjs";

const loadMSTPD = window.mstpd.loadMSTPD;
const SVGNS = "http://www.w3.org/2000/svg";
const UNIT = 110; // grid cell -> px
const NODE_RADIUS = 24; // node radius in px
const NO_STP_RADIUS = 16; // half the side of a bridge that runs no protocol
const PORT_MARKER_OFFSET = NODE_RADIUS + 9; // how far from a node's centre its port marker sits
const PAD = NODE_RADIUS + 24; // viewBox margin around the nodes
const MAX_STRETCH = 2; // how far one axis of the grid may be pulled to fill the box
const PARALLEL_GAP = 16; // px between parallel links joining the same pair
const SLOW_FACTOR = 3; // how much the snail stretches each simulated second
const MAX_WAVES = 50; // give up on a cascade that never settles
const LOOKAHEAD_PAD = 10; // seconds the peek adds to the timers, to be safe

// Port/link state -> colour
const STATE_COLOR = {
  forwarding: "#2a7",
  learning: "#d90",
  listening: "#d90",
  blocking: "#e55",
  discarding: "#e55",
};
const colorFor = (s) => STATE_COLOR[s] || "#888";

// Shown on the Start half of the run toggle, and put back when it stops.
const RUN_TITLE = "Play steps one after another";

const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

// -- grammar --------------------------------------------------------

function parseOpts(s) {
  const o = {};
  for (const tok of (s || "").trim().split(/\s+/)) {
    if (!tok) continue;
    const eq = tok.indexOf("=");
    if (eq >= 0) o[tok.slice(0, eq).toLowerCase()] = tok.slice(eq + 1);
    else o[tok.toLowerCase()] = true;
  }
  return o;
}

// Endpoint flag -> the addPort() options it sets. A network port is switch
// facing, so auto-edge has no business turning it into an edge.
const PORT_FLAGS = {
  edge: { edge: true },
  "no-auto-edge": { autoEdge: false },
  network: { network: true, autoEdge: false },
  "bpdu-guard": { bpduGuard: true },
  "root-guard": { restrictedRole: true },
  "no-p2p": { p2p: false },
};

function parseTopology(text) {
  const nodes = [];
  const links = [];
  const errors = [];
  const directives = { protocol: "rstp" };
  const seen = new Set();

  text.split(/\r?\n/).forEach((raw, i) => {
    const line = raw
      .replace(/#.*$/, "")
      .replace(/\/\/.*$/, "")
      .trim();
    if (!line) return;
    const ln = i + 1;

    // Global options
    if (line[0] === ":") {
      const [key, ...rest] = line.slice(1).split(/\s+/);
      const val = rest.join(" ");
      switch (key.toLowerCase()) {
        case "protocol":
          directives.protocol = val.toLowerCase();
          break;
        case "forward-delay":
          directives.forwardDelay = +val;
          break;
        case "max-age":
          directives.maxAge = +val;
          break;
        case "max-hops":
          directives.maxHops = +val;
          break;
        case "tx-hold":
          directives.txHoldCount = +val;
          break;
        case "demo":
          directives.demo = true;
          break;
        default:
          errors.push(`line ${ln}: unknown directive :${key}`);
      }
      return;
    }

    // Links
    let m;
    if ((m = line.match(/^(\S+)\s*(--|->)\s*(\S+)\s*(.*)$/))) {
      const [a, op, b] = [m[1], m[2], m[3]];
      const link = {
        a,
        b,
        oneway: op === "->",
        cost: undefined,
        down: false,
        hazard: 1,
        aOpts: {},
        bOpts: {},
        line: ln,
      };
      for (const tok of m[4].trim().split(/\s+/)) {
        if (!tok) continue;
        const eq = tok.indexOf("=");
        const key = (eq >= 0 ? tok.slice(0, eq) : tok).toLowerCase();
        const val = eq >= 0 ? tok.slice(eq + 1) : true;
        const colon = key.indexOf(":");
        if (colon >= 0) {
          const who = key.slice(0, colon);
          const flag = key.slice(colon + 1);
          const target =
            who === a.toLowerCase()
              ? link.aOpts
              : who === b.toLowerCase()
                ? link.bOpts
                : null;
          if (!target) errors.push(`line ${ln}: ${who} is not an endpoint`);
          else if (!PORT_FLAGS[flag])
            errors.push(`line ${ln}: unknown port flag ${flag}`);
          else Object.assign(target, PORT_FLAGS[flag]);
        } else if (key === "cost") {
          link.cost = +val;
        } else if (key === "hazard") {
          link.hazard = +val;
        } else if (key === "down") {
          link.down = true;
        } else {
          errors.push(`line ${ln}: unknown link option ${key}`);
        }
      }
      links.push(link);
      return;
    }

    // Nodes
    if ((m = line.match(/^(\S+)\s+@\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*(.*)$/))) {
      const name = m[1];
      if (seen.has(name)) {
        errors.push(`line ${ln}: duplicate node ${name}`);
        return;
      }
      seen.add(name);
      const opts = parseOpts(m[4]);
      nodes.push({
        name,
        x: +m[2],
        y: +m[3],
        prio: opts.prio != null ? +opts.prio : undefined,
        proto:
          typeof opts.proto === "string" ? opts.proto.toLowerCase() : undefined,
        icon: typeof opts.icon === "string" ? opts.icon : undefined,
        line: ln,
      });
      return;
    }

    errors.push(`line ${ln}: cannot parse "${line}"`);
  });

  for (const l of links) {
    if (!seen.has(l.a)) errors.push(`line ${l.line}: unknown node ${l.a}`);
    if (!seen.has(l.b)) errors.push(`line ${l.line}: unknown node ${l.b}`);
  }

  return {
    directives,
    nodes,
    links: links.filter((l) => seen.has(l.a) && seen.has(l.b)),
    errors,
  };
}

// -- DOM helpers ----------------------------------------------------

function svgEl(name, attrs = {}, parent) {
  const e = document.createElementNS(SVGNS, name);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

function h(tag, opts = {}, ...kids) {
  const e = document.createElement(tag);
  if (opts.class) e.className = opts.class;
  if (opts.text != null) e.textContent = opts.text;
  if (opts.html != null) e.innerHTML = opts.html;
  if (opts.title) e.title = opts.title;
  if (opts.onclick) e.onclick = opts.onclick;
  for (const k of kids) if (k) e.appendChild(k);
  return e;
}

// The trailing space lives inside, so it goes away with the icon.
const icon = (e) => `<i class="mstp-icon">${e} </i>`;

// Hello time is left out: the core only accepts 2 seconds.
const timersOf = (d) => ({
  forwardDelay: d.forwardDelay,
  maxAge: d.maxAge,
  maxHops: d.maxHops,
  txHoldCount: d.txHoldCount,
});

// Widgets render inside a shadow root to ensure host page's CSS does not impact
// it.
let widgetSheet;
function widgetStyleSheet() {
  if (widgetSheet) return widgetSheet;
  widgetSheet = new CSSStyleSheet();
  for (const sheet of document.styleSheets) {
    let rules;
    try {
      rules = [...sheet.cssRules];
    } catch {
      continue; // cross-origin sheet we're not allowed to read
    }
    if (rules.some((r) => r.cssText.includes(".mstp-topo"))) {
      widgetSheet.replaceSync(rules.map((r) => r.cssText).join("\n"));
      break;
    }
  }
  return widgetSheet;
}

// -- single widget --------------------------------------------------

async function mount(el) {
  if (el.dataset.mstpMounted) return;
  el.dataset.mstpMounted = "1";

  // A <div> wrapper holds its definition in a nested <pre><code> block.
  const code = el.querySelector(":scope > pre > code");
  const source = (code || el).textContent;
  const model = parseTopology(source);

  const root = h("div", { class: "mstp-topo" });
  const bar = h("div", { class: "mstp-bar" });
  const runBtn = h("button", {
    class: "mstp-btn mstp-toggle mstp-primary",
    title: RUN_TITLE,
    html: `<span>${icon("▶️")}Start</span><span>${icon("⏹️")}Stop</span>`,
  });
  const backBtn = h("button", {
    class: "mstp-btn",
    title: "Undo the last step",
    html: `${icon("↩️")}Back`,
  });
  const stepBtn = h("button", {
    class: "mstp-btn",
    title: "Play one step",
    html: `${icon("➡️")}Step`,
  });
  const resetBtn = h("button", {
    class: "mstp-btn",
    title: "Start the simulation over from t=0s",
    html: `${icon("🔄")}Reset`,
  });
  const editBtn = h("button", {
    class: "mstp-btn",
    title: "Edit the topology definition",
    html: `${icon("✏️")}Edit`,
  });
  const saveBtn = h("button", {
    class: "mstp-btn mstp-accent",
    title: "Adopt the edited definition and rebuild",
    html: `${icon("💾")}Save`,
  });
  const discardBtn = h("button", {
    class: "mstp-btn",
    title: "Close the editor and keep the current definition",
    html: `${icon("🗑️")}Discard`,
  });
  runBtn.disabled =
    backBtn.disabled =
    stepBtn.disabled =
    resetBtn.disabled =
      true;
  saveBtn.hidden = discardBtn.hidden = true;
  const clockTime = h("span", { text: "t=0s" });
  const clockBpdu = h("span", { text: "0 BPDUs" });
  const clockConv = h("span", { class: "mstp-clock-c" });
  const clock = h(
    "span",
    { class: "mstp-clock" },
    h("span", { class: "mstp-clock-t" }, clockTime),
    h("span", { class: "mstp-clock-b" }, clockBpdu),
    clockConv,
  );
  const slowBox = document.createElement("input");
  slowBox.type = "checkbox";
  const slow = h(
    "label",
    {
      class: "mstp-slow",
      title: "Slow motion: make each second longer to follow the BPDUs",
    },
    slowBox,
    h("span", { text: "🐌" }),
  );
  bar.append(
    runBtn,
    backBtn,
    stepBtn,
    resetBtn,
    editBtn,
    saveBtn,
    discardBtn,
    clock,
    slow,
  );

  const stage = h("div", { class: "mstp-stage" });
  const svg = svgEl("svg", { preserveAspectRatio: "xMidYMid meet" });
  const canvas = h("div", { class: "mstp-canvas" }, svg);
  const panel = h("div", { class: "mstp-panel" });
  const panelBody = h("div", { class: "mstp-panel-body" });

  // The demo characters, over the diagram.
  const stanEl = h("div", { class: "mstp-sprite mstp-stan" });
  const blobbyEl = h("div", { class: "mstp-sprite mstp-blobby" });
  const spritesEl = h("div", { class: "mstp-sprites" }, blobbyEl, stanEl);
  canvas.appendChild(spritesEl);

  // The editor takes the place of the details while the definition is being
  // changed, so the diagram stays where it is.
  const textarea = h("textarea", { class: "mstp-edit-area" });
  textarea.spellcheck = false;
  textarea.setAttribute("aria-label", "Topology definition");
  textarea.hidden = true;
  panel.append(panelBody, textarea);
  const legend = h("div", { class: "mstp-legend" });
  stage.append(canvas, panel);

  const errBox = h("div", { class: "mstp-errors" });
  errBox.hidden = true;

  root.append(bar, stage, legend, errBox);

  const host = h("div", { class: "mstp-host lf-fullbleed" });
  const shadow = host.attachShadow({ mode: "open" });
  shadow.adoptedStyleSheets = [widgetStyleSheet()];
  shadow.append(root);
  el.replaceWith(host);

  const w = {
    model,
    source,
    root,
    host,
    svg,
    canvas,
    panel: panelBody,
    legend,
    textarea,
    errBox,
    stanEl,
    blobbyEl,
    spritesEl,
    runBtn,
    backBtn,
    stepBtn,
    resetBtn,
    editBtn,
    saveBtn,
    discardBtn,
    clockTime,
    clockBpdu,
    clockConv,
    slowBox,
    speed: 1, // real seconds per simulated second (snail bumps it to SLOW_FACTOR)
    mstp: null,
    nodes: [],
    links: [],
    selected: null,
    flagsOpen: new Set(), // ports whose flag/state details are unfolded, by name
    editing: false,
    demoOn: false, // the demo plays, with the controls and the BPDUs hidden
    demo: null, // its two characters, while it plays
    timerError: false, // the core refused the timers
    time: 0,
    // Convergence: the ports are settled once none of them changes role or
    // state any more. sig is the fingerprint we compare from second to second,
    // actionAt the time of the last cut or restore, changeAt the time of the
    // last change, and settledAt that same time once the peek ahead has shown
    // nothing else is coming (null while the ports are still moving). lookahead
    // is how far that peek goes.
    sig: "",
    lookahead: 0,
    actionAt: 0,
    changeAt: 0,
    settledAt: null,
    bpdus: 0, // BPDUs that have set off since the build
    running: false, // the Start/Stop state
    stepping: false, // a single step is playing, and the loop stops at its end
    raf: null, // animation-loop handle
    clock: 0, // clock in ms (see animate)
    last: 0, // timestamp of the previous frame
    nextAt: 0, // clock time of the next step
    lastClick: { link: null, t: 0 }, // manual double-click detection
    flights: [], // pills flying along the links
    highlight: [], // the BPDUs a control link points an arrow at
    wave: null, // the BPDUs on the wire, and when the last of them lands
    lastSeq: 0, // the newest BPDU already turned into a pill
    // Step back: every op applied since the build (a simulated second, a wave
    // delivery, a link cut or restore) goes into history. The cursor is how
    // many of them the sim currently shows; it falls behind history.length
    // after a step back, and stepping or running moves it forward again.
    history: [],
    cursor: 0,
  };

  widgets.set(host, w);
  applyShape(w);
  buildLegend(w);
  showErrors(w);

  new ResizeObserver(() => relayout(w)).observe(svg);

  svg.addEventListener("pointerdown", (ev) => {
    if (w.mstp && ev.target === svg) select(w, null);
  });
  runBtn.onclick = () => (w.running ? stopRunning(w) : setRunning(w, true));
  backBtn.onclick = () => stepBack(w);
  stepBtn.onclick = () => stepOnce(w);
  resetBtn.onclick = () => {
    setRunning(w, false);
    build(w);
    select(w, null);
    animateSlide(w);
  };
  wireEditor(w);
  slowBox.onchange = () => setSlow(w, slowBox.checked);
  clock.addEventListener("dblclick", () => copySeekLink(w, clock));

  try {
    w.mstp = await loadMSTPD({
      print: () => {},
      printErr: () => {},
    });
    build(w);
    select(w, null);
    w.runBtn.disabled = w.stepBtn.disabled = w.resetBtn.disabled = false;
    if (model.directives.demo) startDemo(w);
  } catch (e) {
    panelBody.textContent = "Failed to load simulation: " + e;
    console.error(e);
    build(w);
  }
  return w;
}

// -- sticky ---------------------------------------------------------
//
// A topology stays at the top of the window while the text about it goes past.
// Once its top edge would leave the window, the widget is taken out of the flow
// and pinned there. Its host stays behind and keeps the height it had, so the
// page does not move. The next heading, or the next topology, pushes the widget
// back out as it comes up.
const { scheduleSticky } = (() => {
  // What puts an end to a topology's stay at the top of the window.
  const STOPPER = "h1, h2, h3, h4, h5, h6, .mstp-host";

  // How far down the window the widget may reach: the top of what comes next,
  // margin included, so the widget does not sit on the air above a heading.
  function stopAt(el) {
    const top = el.getBoundingClientRect().top;
    return top - (parseFloat(getComputedStyle(el).marginTop) || 0);
  }

  // Pin a widget at the top of the window, or put it back in the page. rect is
  // where its host sits, and stop how far down the window the widget may reach.
  function setStuck(w, rect, stop) {
    if (!rect) {
      w.root.classList.remove("mstp-stuck");
      w.root.style.top = w.root.style.left = w.root.style.width = "";
      w.host.style.height = "";
      return;
    }
    // The width comes first, since a narrower widget has a shorter diagram, and
    // the height is read with it. The host takes that height before the widget
    // leaves the flow: a host with nothing in it and no height, even for the
    // length of a measure, makes the browser move the page under our feet.
    w.root.style.left = `${rect.left}px`;
    w.root.style.width = `${rect.width}px`;
    const height = w.root.getBoundingClientRect().height;
    w.host.style.height = `${height}px`;
    w.root.style.top = `${Math.min(0, stop - height)}px`;
    w.root.classList.add("mstp-stuck");
  }

  // Go over the topologies and pin or release each of them. A pinned widget
  // leaves its host where it was, so what is measured here is always the place
  // the page gives the topology, not the place it is drawn at. Widgets in demo
  // mode are not pinned.
  function updateSticky() {
    const els = [...document.querySelectorAll(STOPPER)];
    els.forEach((el, i) => {
      const w = widgets.get(el);
      if (!w) return;
      const rect = el.getBoundingClientRect();
      const stop = els[i + 1] ? stopAt(els[i + 1]) : Infinity;
      // Above the window, and with something left of the room before the next
      // heading or topology.
      if (w.demoOn || rect.top >= 0 || stop <= 0) return setStuck(w, null);
      setStuck(w, rect, stop);
    });
  }

  let pending = false;

  // Scrolling fires far more often than the screen is drawn, so the work waits
  // for the next frame.
  function scheduleSticky() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      updateSticky();
    });
  }

  window.addEventListener("scroll", scheduleSticky, { passive: true });
  window.addEventListener("resize", scheduleSticky);

  return { scheduleSticky };
})();

// -- layout ---------------------------------------------------------

// The room the grid takes, margin included.
function gridExtent(w) {
  const xs = w.model.nodes.map((n) => n.x * UNIT);
  const ys = w.model.nodes.map((n) => n.y * UNIT);
  const x0 = Math.min(0, ...xs);
  const y0 = Math.min(0, ...ys);
  return {
    x0,
    y0,
    spanX: Math.max(0, ...xs) - x0,
    spanY: Math.max(0, ...ys) - y0,
  };
}

// Apply the aspect ratio matching the grid definition.
function applyShape(w) {
  const { spanX, spanY } = gridExtent(w);
  w.svg.style.aspectRatio = `${spanX + 2 * PAD} / ${spanY + 2 * PAD}`;
}

// Layout the bridges in the widget. Nodes can spread a bit to use more space.
function layout(w) {
  const { x0, y0, spanX, spanY } = gridExtent(w);
  const contentW = spanX + 2 * PAD;
  const contentH = spanY + 2 * PAD;
  const box = w.svg.getBoundingClientRect();
  const scale =
    box.width && box.height
      ? Math.min(box.width / contentW, box.height / contentH)
      : 0;
  const vbW = scale ? box.width / scale : contentW;
  const vbH = scale ? box.height / scale : contentH;

  const extraX = Math.min(vbW - contentW, spanX * (MAX_STRETCH - 1));
  const extraY = Math.min(vbH - contentH, spanY * (MAX_STRETCH - 1));
  const stretchX = spanX ? (spanX + extraX) / spanX : 1;
  const stretchY = spanY ? (spanY + extraY) / spanY : 1;
  // Room an axis does not take is split between its two sides.
  const left = PAD + (vbW - contentW - extraX) / 2;
  const top = PAD + (vbH - contentH - extraY) / 2;

  w.nodes.forEach((n, i) => {
    const md = w.model.nodes[i];
    n.x = left + (md.x * UNIT - x0) * stretchX;
    n.y = top + (md.y * UNIT - y0) * stretchY;
  });
  w.svg.setAttribute("viewBox", `0 0 ${vbW} ${vbH}`);
}

// Recompute the layout.
function relayout(w) {
  if (!w.nodes.length) return;
  layout(w);
  render(w);
  movePills(w);
}

// The protocols in play: what each bridge asks for, or the global default. A
// bridge running no protocol at all is not one of them.
function protocolsUsed(w) {
  const protos = new Set(
    w.model.nodes.map((n) => n.proto || w.model.directives.protocol),
  );
  protos.delete("none");
  return protos;
}

function buildLegend(w) {
  w.legend.replaceChildren();
  const protos = protocolsUsed(w);
  const hasStp = protos.has("stp");
  const hasRapid = protos.has("rstp") || protos.has("mstp");
  // Rapid transitions skip learning, so it only shows in STP or on a link
  // forced off p2p, where the rapid handshake cannot happen.
  const hasSlowLink = w.model.links.some(
    (l) => l.aOpts.p2p === false || l.bOpts.p2p === false,
  );

  const entries = [["forwarding", colorFor("forwarding")]];
  if (hasStp || hasSlowLink) entries.push(["learning", colorFor("learning")]);
  entries.push([
    hasStp && hasRapid
      ? "blocking/discarding"
      : hasStp
        ? "blocking"
        : "discarding",
    colorFor("blocking"),
  ]);

  // Port states
  const stateSet = h("div", { class: "mstp-legend-set" });
  for (const [label, color] of entries) {
    const sw = h("i");
    sw.style.background = color;
    stateSet.appendChild(h("span", {}, sw, document.createTextNode(label)));
  }
  w.legend.append(stateSet, h("span", { class: "mstp-sep" }));

  // BPDU types
  const pillSet = h("div", { class: "mstp-legend-set" });
  const pills = [["hello", BPDU_COLOR.hello]];
  if (hasRapid) {
    pills.push(["proposal", BPDU_COLOR.proposal]);
    pills.push(["agreement", BPDU_COLOR.agreement]);
  }
  for (const [label, color] of pills) {
    const dot = h("i", { class: "mstp-dot" });
    dot.style.background = color;
    pillSet.appendChild(h("span", {}, dot, document.createTextNode(label)));
  }
  const ring = h("i", { class: "mstp-dot" });
  ring.style.background = "transparent";
  // The swatch is sized in em, so the ring has to be too, or it turns into a
  // blob once the legend shrinks.
  ring.style.border = `0.15em solid ${BPDU_COLOR.tc}`;
  pillSet.appendChild(
    h("span", {}, ring, document.createTextNode("topology change")),
  );
  w.legend.appendChild(pillSet);
}

// Error message if there is an issue with timers
const TIMER_ERROR =
  "timers rejected, using the defaults: max age must be between 6 and 40, " +
  "forward delay between 4 and 30, max hops between 6 and 100, " +
  "tx hold count between 1 and 10, and 2 * (forward delay - 1) >= max age";

function showErrors(w) {
  const errors = [...w.model.errors];
  if (w.timerError) errors.push(TIMER_ERROR);
  w.errBox.replaceChildren();
  if (!errors.length) {
    w.errBox.hidden = true;
    return;
  }
  w.errBox.hidden = false;
  w.errBox.append(
    h("strong", { text: "Topology errors:" }),
    ...errors.map((e) => h("div", { text: e })),
  );
}

// -- editing --------------------------------------------------------
//
const { wireEditor, leaveEdit } = (() => {
  function enterEdit(w) {
    setRunning(w, false);
    w.textarea.value = w.source;
    w.editing = true;
    w.panel.hidden = true;
    w.textarea.hidden = false;
    w.runBtn.hidden =
      w.backBtn.hidden =
      w.stepBtn.hidden =
      w.resetBtn.hidden =
      w.editBtn.hidden =
        true;
    w.saveBtn.hidden = w.discardBtn.hidden = false;
    w.textarea.focus();
  }

  // Discard: drop the edits and return to the running diagram unchanged.
  function leaveEdit(w) {
    w.editing = false;
    w.textarea.hidden = true;
    w.panel.hidden = false;
    w.runBtn.hidden =
      w.backBtn.hidden =
      w.stepBtn.hidden =
      w.resetBtn.hidden =
      w.editBtn.hidden =
        false;
    w.saveBtn.hidden = w.discardBtn.hidden = true;
  }

  // Save: adopt the edited definition, re-lay the diagram, and rebuild the core.
  function saveEdit(w) {
    w.source = w.textarea.value;
    w.model = parseTopology(w.source);
    applyShape(w);
    buildLegend(w);
    showErrors(w);
    leaveEdit(w);
    build(w);
    if (w.mstp) select(w, null);
    scheduleSticky(); // a new definition means a diagram of another shape
  }

  // Edit opens the editor, Save adopts what it holds and Discard drops it.
  function wireEditor(w) {
    w.editBtn.onclick = () => enterEdit(w);
    w.saveBtn.onclick = () => saveEdit(w);
    w.discardBtn.onclick = () => leaveEdit(w);
  }

  return { wireEditor, leaveEdit };
})();

function build(w) {
  // The rebuild can trip browser scroll anchoring and move the page even
  // though nothing changed size. Note the scroll position to put it back.
  const y0 = window.scrollY;

  const { mstp, model } = w;
  for (const n of w.nodes) n.bridge?.delete();
  w.nodes = [];
  w.links = [];
  w.timerError = false;
  w.time = 0;
  w.bpdus = 0;
  w.selected = null;
  w.flights = [];
  w.highlight = [];
  w.wave = null;
  w.lastSeq = 0;
  w.history = [];
  w.cursor = 0;
  w.svg.querySelector(".mstp-pills")?.remove();

  const byName = new Map();
  const timers = timersOf(model.directives);
  for (const md of model.nodes) {
    const protocol = md.proto || model.directives.protocol;
    const stp = protocol !== "none";
    let bridge = null;
    if (mstp) {
      bridge = mstp.createBridge(md.name, {
        priority: md.prio,
        protocol: stp ? protocol : undefined,
        configId: protocol === "mstp" ? { revision: 1, name: "r1" } : undefined,
      });
      if (bridge.setTimes(timers) < 0) w.timerError = true;
      // A bridge is created with the protocol off, so leave it that way for
      // proto=none: the ports still come up, but nothing drives them.
      if (stp) bridge.enable();
    }
    const node = {
      name: md.name,
      x: 0, // set by layout(), which spreads the grid over the box
      y: 0,
      prio: md.prio,
      protocol,
      icon: md.icon,
      bridge,
      ports: [],
      nextPort: 1,
    };
    w.nodes.push(node);
    byName.set(md.name, node);
  }

  for (const ld of model.links) {
    const a = byName.get(ld.a);
    const b = byName.get(ld.b);
    let pa = null;
    let pb = null;
    let link;
    if (mstp) {
      pa = a.bridge.addPort(`${a.name}.${a.nextPort}`, {
        portno: a.nextPort++,
        cost: ld.cost,
        ...ld.aOpts,
      });
      pb = b.bridge.addPort(`${b.name}.${b.nextPort}`, {
        portno: b.nextPort++,
        cost: ld.cost,
        ...ld.bOpts,
      });
      pa.enable();
      pb.enable();
      link = mstp.link(pa, pb);
      if (ld.oneway) mstp.linkOneWay(pa, pb);
      else if (ld.down) link.break();
      a.ports.push(pa);
      b.ports.push(pb);
    } else {
      link = { broken: ld.down, toggle() {}, break() {}, restore() {} };
    }
    w.links.push({
      a,
      b,
      aPort: pa,
      bPort: pb,
      link,
      cost: ld.cost,
      hazard: ld.hazard, // how much the demo favours this cable
      oneway: ld.oneway, // this link can have a one-way fault
      faulty: ld.oneway, // and the fault is set right now
    });
  }

  // Record every BPDU from now on so the panel can offer a pcap download. A
  // rebuild starts a fresh capture.
  if (mstp) mstp.capture();
  w.lookahead = lookaheadFor(w);
  markAction(w);
  showErrors(w);
  layout(w);
  render(w);
  if (mstp) renderPanel(w);

  // Force a layout to fix scrolling position if needed.
  void w.host.getBoundingClientRect();
  if (window.scrollY !== y0) window.scrollTo({ top: y0, behavior: "instant" });
}

// -- convergence ----------------------------------------------------
//
// The topology has converged once every port has stopped changing role and
// state. BPDUs keep flowing after that (hellos, and the topology change flag
// for a few more seconds), so the ports are what we watch. The core is run on
// ahead to check if the topology changes.

// The role and state of every port, as one string to compare. Each port is read
// on its own: the fingerprint is taken again for every second the peek below
// runs.
function portSig(w) {
  const parts = [];
  for (const n of w.nodes)
    for (const p of n.ports) parts.push(`${p.handle}:${p.role()}:${p.state()}`);
  return parts.join(" ");
}

// How far the peek has to go to be sure. A port waits two forward delays before
// it forwards, and what a bridge said last takes a max age to expire, so nothing
// can happen later than that.
function lookaheadFor(w) {
  const b0 = snapshot(w).topo?.bridges[0];
  return b0 ? 2 * b0.forward_delay + b0.max_age + LOOKAHEAD_PAD : 0;
}

// Room to keep the core's memory during a peek. Only one widget peeks at a
// time, so a single buffer, as large as the largest core met so far, does.
let peekBuf = new Uint8Array(0);

// Run the core ahead and tell whether the ports keep the fingerprint they have
// now. Everything the core knows sits in its WebAssembly memory, so a copy of
// it, put back at the end, undoes the peek.
function portsStayPut(w, sig) {
  const heap = w.mstp.m.HEAPU8;
  if (peekBuf.length < heap.length) peekBuf = new Uint8Array(heap.length);
  peekBuf.set(heap);
  let same = true;
  for (let i = 0; i < w.lookahead && same; i++) {
    w.mstp.step(1);
    same = portSig(w) === sig;
  }
  // Growing the memory hands out a new view, so ask for it again.
  const back = w.mstp.m.HEAPU8;
  back.set(peekBuf.subarray(0, back.length));
  return same;
}

// Start measuring again: on a rebuild, and on every link cut or restore. The
// ports the link touches change right away, so that is not a change to count.
function markAction(w) {
  w.sig = portSig(w);
  w.actionAt = w.changeAt = w.time;
  w.settledAt = null;
  renderClock(w);
}

// After a second has been simulated, with nothing left on the wire: note
// whether anything moved, and record the convergence time as soon as the ports
// are done moving. Called once per second.
function trackConvergence(w) {
  const sig = portSig(w);
  if (sig !== w.sig) {
    w.sig = sig;
    w.changeAt = w.time;
    w.settledAt = null;
  }
  if (w.settledAt === null && portsStayPut(w, sig)) w.settledAt = w.changeAt;
}

// -- history / step back --------------------------------------------
//
// The core cannot rewind, but it is deterministic: a fresh build replayed
// through the same ops lands in the same state. So stepping back rebuilds the
// sim and re-applies the history, one op short. While the cursor is behind the
// tip, stepping or running forward replays the recorded ops (the cuts and
// restores come from the history, the rest the sim reproduces on its own) until
// the sim is live again.

// Note an op in the history. Behind the tip, the sim replays the same sequence,
// so the op matches the recorded one and the cursor just moves forward. A new
// action taken from the past crop the history to the current point.
function record(w, t, link) {
  if (w.demoOn) return;
  const next = w.history[w.cursor];
  if (next && next.t === t && next.link === link) {
    w.cursor += 1;
    return;
  }
  w.history.length = w.cursor;
  w.history.push({ t, link });
  w.cursor = w.history.length;
}

// Re-apply one recorded op without animation. Pills that were flying land
// straight away: they are counted as sent and dropped, and only the last op's
// BPDUs stay pending on the wire.
function applyOp(w, op) {
  if (op.t === "toggle") {
    applyToggle(w, w.links[op.link]);
    return;
  }
  w.bpdus += w.flights.length;
  w.flights = [];
  let gen = 0;
  if (op.t === "tick") {
    w.time += 1;
    w.mstp.oneSecond();
  } else {
    gen = w.wave ? w.wave.gen + 1 : 0;
    w.mstp.deliverBPDUs();
  }
  emitWave(w, gen);
  if (gen >= MAX_WAVES) {
    w.wave = null;
    w.bpdus += w.flights.length;
    w.flights = [];
  }
  if (!w.wave) trackConvergence(w);
}

// Apply one step the way the Step button plays it, but without animation:
// deliver a pending wave, or run a second and deliver whatever it sends.
function applyStep(w) {
  if (w.wave) {
    record(w, "deliver");
    applyOp(w, { t: "deliver" });
    return;
  }
  record(w, "tick");
  applyOp(w, { t: "tick" });
  if (w.wave) {
    record(w, "deliver");
    applyOp(w, { t: "deliver" });
  }
}

// Rebuild the core and silently replay the first cursor ops. The selection is
// carried over to the rebuilt nodes and links.
function replay(w) {
  const { history, cursor, selected } = w;
  const sel =
    selected &&
    (selected.type === "link"
      ? { type: "link", index: w.links.indexOf(selected.ref) }
      : { type: "node", name: selected.ref.name });
  build(w);
  w.history = history;
  while (w.cursor < cursor) applyOp(w, history[w.cursor++]);
  select(
    w,
    sel &&
      (sel.type === "link"
        ? { type: "link", ref: w.links[sel.index] }
        : { type: "node", ref: w.nodes.find((n) => n.name === sel.name) }),
  );
}

// Copy the diagram as it stands, to slide it out once the rewound one has taken
// its place. The copy is laid over the canvas, so it needs the size it had as
// the only child.
function snapshotCanvas(w) {
  if (reducedMotion.matches) return null;
  const { width, height } = w.svg.getBoundingClientRect();
  if (!width || !height) return null;
  const ghost = w.svg.cloneNode(true);
  ghost.classList.add("mstp-ghost");
  ghost.style.width = `${width}px`;
  ghost.style.height = `${height}px`;
  return ghost;
}

// Push the old diagram out one side while the new one comes in from the other,
// the way the move travels: to the right for a step back, to the left ahead.
function animateSlide(w, ghost, back) {
  w.canvas.querySelector(".mstp-ghost")?.remove();
  w.canvas.classList.remove("mstp-slide", "mstp-slide-fwd");
  if (!ghost) return;
  void w.canvas.offsetWidth; // let the browser catch up, so the slide starts again
  w.canvas.append(ghost);
  w.canvas.classList.add("mstp-slide");
  w.canvas.classList.toggle("mstp-slide-fwd", !back);
  ghost.addEventListener(
    "animationend",
    () => {
      ghost.remove();
      w.canvas.classList.remove("mstp-slide", "mstp-slide-fwd");
    },
    { once: true },
  );
}

// The step number now on show. A step is one Step press: a tick, or a lone
// deliver (a deliver that lands a wave an earlier tick sent belongs to that
// tick's step). A toggle is not a step, so a link cut leaves the number alone.
function stepNumber(w) {
  let n = 0;
  for (let i = 0; i < w.cursor; i++) {
    const t = w.history[i].t;
    if (t === "tick" || (t === "deliver" && w.history[i - 1]?.t !== "tick"))
      n++;
  }
  return n;
}

// How far along the history the widget stands: the steps on show, plus the cuts
// and restores, which are not steps but still move the state on.
function historyPos(w) {
  let n = stepNumber(w);
  for (let i = 0; i < w.cursor; i++) if (w.history[i].t === "toggle") n += 1;
  return n;
}

// Move one step back: undo the step now on show. A deliver that landed a tick's
// wave goes with that tick, a lone deliver or a toggle on its own.
function stepBack(w) {
  if (!w.mstp || w.raf || w.cursor === 0) return;
  const ghost = snapshotCanvas(w);
  w.cursor -= 1;
  if (
    w.history[w.cursor].t === "deliver" &&
    w.history[w.cursor - 1]?.t === "tick"
  )
    w.cursor -= 1;
  replay(w);
  animateSlide(w, ghost, true);
}

// The back button only works at rest, with at least one op to rewind.
function updateBackBtn(w) {
  w.backBtn.disabled = !w.mstp || w.raf !== null || w.cursor === 0;
}

// -- running --------------------------------------------------------

// Only one topology on the page runs at a time (demo excluded).
let activeWidget = null;

// Start a simulated second: run the timers, then put whatever the bridges
// transmit on the wire.
function stepTick(w) {
  if (!w.mstp) return;
  record(w, "tick");
  w.time += 1;
  w.nextAt = w.clock + 1000;

  w.mstp.oneSecond();
  emitWave(w, 0);
  if (!w.wave) endTick(w); // a quiet second: no BPDU to wait for
  redrawState(w);
}

// The wave has landed: hand the frames to the bridges and send whatever they
// answer with on its way.
function deliverWave(w) {
  record(w, "deliver");
  const gen = w.wave.gen + 1;
  w.wave = null;
  w.mstp.deliverBPDUs();
  emitWave(w, gen);
  if (gen >= MAX_WAVES) w.wave = null;
  if (!w.wave) endTick(w);
  redrawState(w);
}

// Nothing is left on the wire: note whether the ports moved, and leave a short
// pause before the next second starts.
function endTick(w) {
  trackConvergence(w);
  renderClock(w);
  w.nextAt = Math.max(w.nextAt, w.clock + 150);
}

// Redraw the diagram with the state currently on show.
function redrawState(w) {
  render(w);
  renderPanel(w);
}

// A BPDU is counted as its pill sets off, not when it is put on the wire: a wave
// is handed over at the end of a step and only leaves on the next one, and a
// number climbing while nothing moves is a puzzle.
function countLaunched(w, from) {
  const n = w.flights.filter(
    (f) => f.start >= from && f.start < w.clock,
  ).length;
  if (!n) return;
  w.bpdus += n;
  renderClock(w);
}

// The animation loop. One requestAnimationFrame runs the whole time we play.
// Each frame it moves the clock on, does any due redraw or step, and draws the
// pills. It reads the speed each frame, so the snail also affects pills already
// flying.
function animate(w, now) {
  const dt = now - w.last;
  w.last = now;
  const from = w.clock;
  // Slower (by speed) while pills fly, real time when idle.
  w.clock += dt / (w.flights.length ? w.speed : 1);

  countLaunched(w, from);
  w.flights = w.flights.filter((f) => w.clock < f.start + FLIGHT_MS);

  // Replaying: a recorded cut or restore comes back at its place between the
  // seconds and waves around it.
  while (w.cursor < w.history.length && w.history[w.cursor].t === "toggle") {
    const op = w.history[w.cursor];
    w.cursor += 1;
    applyToggle(w, w.links[op.link]);
    redrawState(w);
  }

  if (w.demoOn) demoFrame(w, dt);
  else if (w.wave) {
    // A step ends once the BPDUs it was playing have been delivered.
    if (w.clock >= w.wave.landAt) {
      deliverWave(w);
      if (w.stepping) return endStep(w);
    }
  } else if (w.clock >= w.nextAt) {
    stepTick(w); // start the next second
    // A second nobody had anything to say in is a step of its own.
    if (w.stepping && !w.wave) return endStep(w);
  }

  drawPills(w);
  w.raf = requestAnimationFrame((t) => animate(w, t));
}

function startLoop(w) {
  if (!w.demoOn) {
    if (activeWidget && activeWidget !== w) setRunning(activeWidget, false);
    activeWidget = w;
  }
  w.last = performance.now();
  w.raf = requestAnimationFrame((t) => animate(w, t));
  w.stepBtn.disabled = true;
  updateBackBtn(w);
}

function stopLoop(w) {
  cancelAnimationFrame(w.raf);
  w.raf = null;
  if (activeWidget === w) activeWidget = null;
  w.stepBtn.disabled = !w.mstp;
  updateBackBtn(w);
}

// Play one step: send the BPDUs waiting on the wire across their links and
// deliver them. With nothing to send, run the next second instead, and do not
// sit through what is left of the current one.
function stepOnce(w) {
  if (!w.mstp || w.raf) return;
  // Replaying: a recorded cut or restore is a step of its own.
  const next = w.history[w.cursor];
  if (next && next.t === "toggle") {
    w.cursor += 1;
    applyToggle(w, w.links[next.link]);
    redrawState(w);
    return;
  }
  w.stepping = true;
  if (!w.wave) w.nextAt = w.clock;
  startLoop(w);
}

// The step is over. Whatever it has just put on the wire waits there for the
// next one, so leave it alone.
function endStep(w) {
  w.stepping = false;
  drawPills(w);
  stopLoop(w);
}

// When stopping, just toggle the running flag and finish the current step if
// any. Otherwise, just stop where we are.
function stopRunning(w) {
  if (w.raf && w.wave) {
    w.running = false;
    w.stepping = true;
    showRunning(w, false);
    return;
  }
  setRunning(w, false);
}

// The same button reads Start or Stop, so its tooltip follows the state.
function showRunning(w, on) {
  w.runBtn.classList.toggle("mstp-active", on);
  w.root.classList.toggle("mstp-running", on);
  w.runBtn.title = on ? "Stop after the current step" : RUN_TITLE;
}

function setRunning(w, on) {
  if (on && !w.running) {
    w.running = true;
    w.stepping = false; // a step in flight simply carries on
    if (!w.raf) {
      w.nextAt = w.clock + 200;
      startLoop(w);
    }
    showRunning(w, true);
    w.stepBtn.disabled = true;
  } else if (!on && (w.running || w.raf)) {
    w.running = w.stepping = false;
    stopLoop(w);
    showRunning(w, false);
  }
}

// Slow motion, with the box kept in step: the loop reads the speed each frame,
// so a change takes effect straight away.
function setSlow(w, on) {
  w.slowBox.checked = on;
  w.speed = on ? SLOW_FACTOR : 1;
}

// -- demo mode ------------------------------------------------------
//
// The topology plays by itself while two characters work on the cables. Stan
// walks to a cable and swings his sword at it until it cuts. Blobby follows him
// to repair the cable and wait for the next cut.
const { startDemo, demoFrame, demoClick } = (() => {
  // The two characters. Each one has a sprite sheet of 64x64 tiles, eight per
  // line, with one line per animation.
  const STAN_ROWS = {
    down: [0, 8], // line number, number of sprites
    left: [1, 8],
    right: [2, 8],
    up: [3, 8],
    attack: [4, 8],
  };
  const BLOBBY_ROWS = {
    down: [0, 8],
    up: [1, 8],
    left: [2, 8],
    right: [3, 8],
    idle: [4, 6],
    repair: [5, 6],
  };
  const TILE = 64; // a tile of a sprite sheet, in px
  const SPRITE_SIZE = 72; // how wide a tile is drawn, in diagram units
  const STAN_SPEED = 50; // diagram units a character covers per second
  const BLOBBY_SPEED = 40;
  const BLOBBY_RUSH = 1.5; // how much faster Blobby goes per extra cable down
  const WALK_FPS = 10;
  const ACT_FPS = 8; // the attack and the repair
  const CUT_CHANCE = 1 / 4; // how often a swing goes through the cable
  const STAN_LIFT = 16; // how far over a cable Stan stands, so his sword meets it
  const REPAIR_LOOPS = 2; // repair animations played before the cable comes back
  const MAX_FRAME_MS = 100; // longest step a frame may take, in real time
  const COFFEE_SIZE = (16 * SPRITE_SIZE) / TILE; // the 16 px cup tile, one sprite pixel per pixel
  const COFFEE_GAP = 16; // how far right of a cable's middle the cup sits

  function startDemo(w) {
    if (w.demoOn) return;
    if (w.editing) leaveEdit(w);
    setRunning(w, false);
    w.demoOn = true;
    w.root.classList.add("mstp-demo");
    build(w);
    w.demo = cast(w);
    // Nobody is watching while the widget is off screen, so the clock comes and
    // goes with it. The observer reports where the widget stands as soon as it
    // is set up, so this is also what gets the demo going.
    new IntersectionObserver(([e]) => setRunning(w, e.isIntersecting)).observe(
      w.host,
    );
    scheduleSticky(); // a demo never stays at the top of the window
  }

  // The two characters, side by side in the bottom left corner where the demo
  // starts them. From there they follow the cables and stay where those leave
  // them.
  function cast(w) {
    const y = w.svg.viewBox.baseVal.height - SPRITE_SIZE / 2;
    return {
      blobby: sprite(w.blobbyEl, BLOBBY_ROWS, BLOBBY_SPEED, SPRITE_SIZE / 2, y),
      stan: sprite(w.stanEl, STAN_ROWS, STAN_SPEED, SPRITE_SIZE * 1.5, y),
      coffee: null,
    };
  }

  // One character. rows is its sheet and speed how fast it crosses the diagram.
  // anim names the line of the sheet it plays, frame the tile in that line and t
  // the time spent on it. link is the cable it works on, mode what it does there,
  // and dir the way it faces while it walks.
  function sprite(el, rows, speed, x, y) {
    return {
      el,
      rows,
      speed,
      x,
      y,
      anim: "down", // whatever it does next puts its own line up
      dir: "down",
      frame: 0,
      t: 0,
      loops: 0,
      mode: "walk",
      link: null,
    };
  }

  // A cable the demo counts as down: a plain link that is cut, or a one-way link
  // with its fault on.
  const isCut = (e) => (e.oneway ? e.faulty : e.link.broken);

  // The middle of a cable, where a character stands to work on it.
  const linkMid = (e) => [
    (e.geom.x1 + e.geom.x2) / 2,
    (e.geom.y1 + e.geom.y2) / 2,
  ];

  // Cut or repair a cable from the demo. Same as a double-click, without the
  // selection a click leaves behind.
  function demoToggle(w, e) {
    applyToggle(w, e);
    redrawState(w);
  }

  // Take the cup away, once it stands by the cable that just went down.
  function takeCoffee(w, e) {
    if (w.demo.coffee?.link !== e) return;
    w.demo.coffee.el.remove();
    w.demo.coffee = null;
  }

  // A click on a cable during the demo: a cup goes by its middle and Stan
  // leaves whatever he was doing to go for that one. A cable already down gets
  // nothing. Only one cup stands at a time, so another click moves it. The cup
  // goes behind the characters, who walk over it.
  function demoClick(w, e) {
    if (isCut(e)) return;
    w.demo.coffee?.el.remove();
    const el = h("div", { class: "mstp-coffee" });
    w.spritesEl.prepend(el);
    w.demo.coffee = { el, link: e };
    w.demo.stan.link = e;
    w.demo.stan.mode = "walk";
  }

  // Move a character towards a point and tell whether it is there. Its heading
  // picks the line of the sheet its walk plays.
  function walkTo(sp, tx, ty, dt) {
    const dx = tx - sp.x;
    const dy = ty - sp.y;
    const dist = Math.hypot(dx, dy);
    const step = (sp.speed * dt) / 1000;
    if (dist <= step) {
      sp.x = tx;
      sp.y = ty;
      return true;
    }
    sp.x += (dx / dist) * step;
    sp.y += (dy / dist) * step;
    if (Math.abs(dx) > Math.abs(dy)) sp.dir = dx > 0 ? "right" : "left";
    else sp.dir = dy > 0 ? "down" : "up";
    return false;
  }

  // Play an animation on: move to the tile the elapsed time asks for, and return
  // how many times the line has been played through since the last call.
  function playFrames(sp, fps, dt) {
    const count = sp.rows[sp.anim][1];
    sp.t += dt;
    const n = Math.floor((sp.t * fps) / 1000);
    sp.t -= (n * 1000) / fps;
    sp.frame += n;
    const loops = Math.floor(sp.frame / count);
    sp.frame %= count;
    return loops;
  }

  // Start another animation from its first tile.
  function playAnim(sp, anim) {
    sp.anim = anim;
    sp.frame = 0;
    sp.t = 0;
    sp.loops = 0;
  }

  // The cable Stan goes for next: one of those still up, except the one where
  // Blobby is.
  function nextVictim(w, spare) {
    const open = w.links.filter((e) => e.hazard > 0); // exclude links with hazard=0
    const up = open.filter((e) => !isCut(e) && e !== spare); // exclude cut links and the link where blobby is
    const pool = up.length ? up : open; // except if there is no remaining link
    let n = Math.random() * pool.reduce((sum, e) => sum + e.hazard, 0); // choose a random number
    return pool.find((e) => (n -= e.hazard) < 0) || null; // choose the link matching the random number (each link has a range matching its weight)
  }

  // Stan never rests: he walks to a cable and swings at it until it gives, then
  // goes for the next one. A swing that misses is simply played again.
  function stepStan(w, sp, dt) {
    if (sp.mode === "attack") {
      if (!playFrames(sp, ACT_FPS, dt)) return;
      if (isCut(sp.link) || Math.random() >= CUT_CHANCE) return;
      demoToggle(w, sp.link);
      takeCoffee(w, sp.link); // he drinks it once the cable is down
      sp.link = null;
      sp.mode = "walk";
      return;
    }
    if (!sp.link) sp.link = nextVictim(w, w.demo.blobby.link);
    if (!sp.link) return;
    const [tx, ty] = linkMid(sp.link);
    if (walkTo(sp, tx, ty - STAN_LIFT, dt)) {
      sp.mode = "attack";
      playAnim(sp, "attack");
      return;
    }
    if (sp.anim !== sp.dir) playAnim(sp, sp.dir);
    playFrames(sp, WALK_FPS, dt);
  }

  // Blobby takes the cables that are down, one at a time, and waits by the last
  // one it repaired.
  function stepBlobby(w, sp, dt) {
    if (sp.mode === "repair") {
      sp.loops += playFrames(sp, ACT_FPS, dt);
      if (sp.loops < REPAIR_LOOPS) return;
      if (isCut(sp.link)) demoToggle(w, sp.link);
      sp.mode = "walk"; // sp.link stays: the repaired cable is where Blobby waits
      return;
    }
    // The cable it is already on its way to while that one is still down, else
    // the next one down. With every cable up, sp.link keeps the last of them and
    // Blobby waits by it.
    const down = sp.link && isCut(sp.link) ? sp.link : w.links.find(isCut);
    if (!down) {
      if (sp.anim !== "idle") playAnim(sp, "idle");
      playFrames(sp, ACT_FPS, dt);
      return;
    }
    sp.link = down;
    sp.speed = BLOBBY_SPEED * BLOBBY_RUSH ** (w.links.filter(isCut).length - 1);
    const [tx, ty] = linkMid(down);
    if (walkTo(sp, tx, ty, dt)) {
      sp.mode = "repair";
      playAnim(sp, "repair");
      return;
    }
    if (sp.anim !== sp.dir) playAnim(sp, sp.dir);
    playFrames(sp, WALK_FPS, dt);
  }

  // How the diagram sits on the canvas: how many px a diagram unit takes, and
  // where the top left corner of the diagram is.
  function demoView(w) {
    const vb = w.svg.viewBox.baseVal;
    const box = w.svg.getBoundingClientRect();
    if (!vb.width || !box.width) return null;
    const canvas = w.canvas.getBoundingClientRect();
    return {
      k: box.width / vb.width,
      ox: box.left - canvas.left,
      oy: box.top - canvas.top,
    };
  }

  // Put a character where it stands. The tile keeps its size in px and the
  // transform does the scaling, so only two properties change per frame.
  function drawSprite(sp, view) {
    const k = (view.k * SPRITE_SIZE) / TILE;
    const x = view.ox + sp.x * view.k - (TILE * k) / 2;
    const y = view.oy + sp.y * view.k - (TILE * k) / 2;
    sp.el.style.transform = `translate(${x}px, ${y}px) scale(${k})`;
    sp.el.style.backgroundPosition = `${-sp.frame * TILE}px ${-sp.rows[sp.anim][0] * TILE}px`;
  }

  // Put a cup beside its cable. The place comes from the cable itself, so the
  // cup follows it when the diagram is laid out again.
  function drawCoffee(c, view) {
    const [mx, my] = linkMid(c.link);
    const side = COFFEE_SIZE * view.k;
    const x = view.ox + (mx + COFFEE_GAP) * view.k - side / 2;
    const y = view.oy + my * view.k - side / 2;
    c.el.style.width = c.el.style.height = `${side}px`;
    c.el.style.transform = `translate(${x}px, ${y}px)`;
  }

  // In demo mode, no need to animate each wave. Let's play all of them at once.
  function demoSecond(w) {
    w.nextAt = w.clock + 1000;
    applyOp(w, { t: "tick" });
    while (w.wave) applyOp(w, { t: "deliver" });
    redrawState(w); // once, at the end
  }

  // One frame of the demo, driven by the animation loop.
  function demoFrame(w, dt) {
    if (w.clock >= w.nextAt) demoSecond(w);
    const view = demoView(w);
    if (!view) return;
    // The first frame of the loop can carry a timestamp older than the moment it
    // was asked for, and a tab coming back to the front a very long one. A step
    // out of range would send a character that stands on its mark nowhere.
    dt = Math.min(Math.max(dt, 0), MAX_FRAME_MS);
    stepStan(w, w.demo.stan, dt);
    stepBlobby(w, w.demo.blobby, dt);
    drawSprite(w.demo.stan, view);
    drawSprite(w.demo.blobby, view);
    if (w.demo.coffee) drawCoffee(w.demo.coffee, view);
  }

  return { startDemo, demoFrame, demoClick };
})();

// -- BPDU animation -------------------------------------------------
//
// A pill is one BPDU on its way across a link. Only what the run loop and
// the legend need leaves this block.
const { BPDU_COLOR, FLIGHT_MS, emitWave, movePills, drawPills } = (() => {
  const FLIGHT_MS = 500; // how long a BPDU takes to cross a link
  const PILL_GAP = 90; // how far apart BPDUs leaving the same port at once set off

  // BPDU type -> colour, for the pills that animate along the links while
  // running. A transmitted BPDU is sorted into exactly one of the base buckets.
  // tc is not a base type but the ring drawn around any pill whose frame also
  // carries a topology change (the TC flag, or a legacy TCN BPDU).
  const BPDU_COLOR = {
    hello: "#3b82f6", // a plain periodic BPDU
    proposal: "#f59e0b", // RST BPDU carrying the proposal flag
    agreement: "#22c55e", // RST BPDU carrying the agreement flag
    tc: "#ef4444", // ring: the frame also carries a topology change
  };

  // The arrow a control link puts on the BPDUs it points out, and how far and
  // how fast it swings towards them.
  const HIGHLIGHT_COLOR = "#dc2626";
  const BOB = 4; // px
  const BOB_MS = 200; // one swing in and out

  // The BPDU each frame carries. A topology change is not a type of its own: the
  // TC flag rides on whatever frame the port was already sending, so it is drawn
  // as a ring around the pill.
  const bpduType = (f) =>
    f.proposal ? "proposal" : f.agreement ? "agreement" : "hello";

  // Which end of which link a port sits at, and where its pills fly to.
  function portGeometry(w) {
    const m = new Map();
    for (const e of w.links) {
      if (!e.geom) continue;
      const { x1, y1, x2, y2 } = e.geom;
      if (e.aPort)
        m.set(e.aPort.handle, { link: e, sx: x1, sy: y1, tx: x2, ty: y2 });
      if (e.bPort)
        m.set(e.bPort.handle, { link: e, sx: x2, sy: y2, tx: x1, ty: y1 });
    }
    return m;
  }

  // Send the BPDUs the core has put on the wire since the last wave on their way,
  // one pill per frame. Every pill takes FLIGHT_MS to cross its link, so they all
  // land together and the wave can then be delivered. Stores the wave on the
  // widget, or null when the bridges had nothing to say.
  function emitWave(w, gen) {
    const frames = w.mstp.queuedBPDUs(w.lastSeq);
    const at = portGeometry(w);
    const now = w.clock;
    const nth = new Map(); // BPDUs a port is sending at once, to stagger them

    for (const f of frames) {
      w.lastSeq = Math.max(w.lastSeq, f.seq);
      const g = at.get(f.src);
      if (!g) continue;
      // Several BPDUs leaving one port at once are spread out a little so they
      // can be told apart.
      const i = nth.get(f.src) || 0;
      nth.set(f.src, i + 1);
      w.flights.push({
        link: g.link,
        src: f.src,
        nth: i,
        sx: g.sx,
        sy: g.sy,
        tx: g.tx,
        ty: g.ty,
        color: BPDU_COLOR[bpduType(f)],
        tc: f.tc,
        start: now + i * PILL_GAP,
      });
    }

    // A cut puts its BPDUs on a wire that may still be carrying the previous ones.
    // The core holds them in one queue, so they make up a single wave, landing
    // when the last of them arrives.
    const landAt = w.flights.reduce(
      (m, f) => Math.max(m, f.start + FLIGHT_MS),
      0,
    );
    w.wave = landAt ? { gen, landAt } : null;
  }

  // Draw each flying pill at its spot for the current clock. The pill layer goes
  // back on top each frame so render()'s redraw does not wipe it.
  function drawPills(w) {
    let layer = w.svg.querySelector(".mstp-pills");
    if (w.demoOn || !w.flights.length) {
      layer?.remove();
      return;
    }
    if (!layer)
      layer = svgEl("g", { class: "mstp-pills", "pointer-events": "none" });
    else layer.replaceChildren();
    w.svg.appendChild(layer);

    for (const f of w.flights) {
      if (w.clock < f.start) continue; // not launched yet
      const p = (w.clock - f.start) / FLIGHT_MS;
      const x = f.sx + (f.tx - f.sx) * p;
      const y = f.sy + (f.ty - f.sy) * p;
      const fade = Math.min(1, p / 0.15, (1 - p) / 0.15);

      if (marked(w, f)) drawArrow(layer, f, x, y, fade, w.clock);
      svgEl(
        "circle",
        {
          cx: x,
          cy: y,
          r: f.tc ? 5 : 4.5,
          fill: f.color,
          stroke: f.tc ? BPDU_COLOR.tc : "#fff8",
          "stroke-width": f.tc ? 2.25 : 0.75,
          opacity: fade,
        },
        layer,
      );
    }
  }

  // Does this pill get an arrow? A mark with no number takes every BPDU its port
  // sends in the same wave.
  const marked = (w, f) =>
    w.highlight.some(
      (m) => m.src === f.src && (m.nth === null || m.nth === f.nth),
    );

  // An arrow travelling with a pill and pointing at it, to single out one BPDU
  // among the many crossing the diagram. It sits to one side of the link so the
  // pill itself stays visible, and nudges towards it and back to catch the eye.
  function drawArrow(layer, f, x, y, opacity, clock) {
    const len = Math.hypot(f.tx - f.sx, f.ty - f.sy) || 1;
    const ux = (f.tx - f.sx) / len;
    const uy = (f.ty - f.sy) / len;
    const bob = (BOB / 2) * (1 - Math.cos((2 * Math.PI * clock) / BOB_MS));
    // Coordinates in the arrow's own frame: out is the distance from the pill,
    // side the offset across the arrow.
    const at = (out, side) => [
      x - uy * (out - bob) + ux * side,
      y + ux * (out - bob) + uy * side,
    ];
    const gap = 10; // between the pill and the tip, at the far end of the swing
    const head = 8; // length of the head
    const total = 24; // pill to tail
    const hw = 6; // half width of the head
    const sw = 2; // half width of the shaft
    svgEl(
      "polygon",
      {
        points: [
          at(gap, 0),
          at(gap + head, hw),
          at(gap + head, sw),
          at(total, sw),
          at(total, -sw),
          at(gap + head, -sw),
          at(gap + head, -hw),
        ]
          .map((p) => p.join(","))
          .join(" "),
        fill: HIGHLIGHT_COLOR,
        stroke: "#fff8",
        "stroke-width": 0.75,
        opacity,
      },
      layer,
    );
  }

  // A resize moves the ends of every link, and the pills on their way carry
  // those ends with them.
  function movePills(w) {
    const at = portGeometry(w);
    for (const f of w.flights) {
      const g = at.get(f.src);
      if (g) ({ sx: f.sx, sy: f.sy, tx: f.tx, ty: f.ty } = g);
    }
  }

  return { BPDU_COLOR, FLIGHT_MS, emitWave, movePills, drawPills };
})();

// -- state ----------------------------------------------------------

function snapshot(w) {
  if (!w.mstp) return { topo: null, bridges: new Map(), ports: new Map() };
  const topo = w.mstp.topology();
  const bridges = new Map();
  const ports = new Map();
  for (const b of topo.bridges) {
    bridges.set(b.handle, b);
    for (const p of b.ports) ports.set(p.handle, p);
  }
  return { topo, bridges, ports };
}

// The node holding a bridge id, or null when it sits outside the widget.
function nodeForBridgeId(w, snap, id) {
  for (const n of w.nodes) {
    const b = snap.bridges.get(n.bridge?.handle);
    if (b && b.bridge_id === id) return n;
  }
  return null;
}

// Add the name of the bridge owning a bridge id: "8192.02:00:00:00:00:04 (E)".
function namedBridgeId(w, snap, id) {
  const n = nodeForBridgeId(w, snap, id);
  return n ? `${id} (${n.name})` : id;
}

// The name of the root bridge a node has elected, after a 本 marker. A root
// sitting outside the widget has no name to show.
function rootName(w, snap, b) {
  const n = nodeForBridgeId(w, snap, b.designated_root);
  return `本${n ? n.name : "?"}`;
}

// A bridge with the spanning tree turned off. The core keeps it disabled: it
// never transmits, and drops whatever it receives.
const noStp = (n) => n.protocol === "none";

// A port with no carrier: its cable is cut, or BPDU guard has shut it down.
const isDown = (ps) => !!ps && !ps.up;

// The role and state of a port whose bridge runs no protocol mean nothing, so
// they are not shown.
const shown = (node, ps) => (noStp(node) ? null : ps);

// Does traffic cross this end of a link? Without a protocol nothing blocks the
// port, so a live cable is enough.
const forwards = (node, ps) =>
  noStp(node) ? !!ps && ps.up : ps?.state === "forwarding";

// The core reports RSTP/MSTP's discarding state as the kernel's "blocking"
// (MSTPD maps it onto BR_STATE_BLOCKING). Show the RSTP name when appropriate.
function stateLabel(w, state) {
  const p = w.model.directives.protocol;
  if (state === "blocking" && (p === "rstp" || p === "mstp"))
    return "discarding";
  return state;
}

// -- rendering ------------------------------------------------------

// Flash an element to catch the eye. Any extra class picks another colour.
function bump(el, ...extra) {
  el.classList.remove("mstp-bump", "mstp-bump-copy");
  void el.offsetWidth; // let the browser catch up, so the flash starts again
  el.classList.add("mstp-bump", ...extra);
}

// Update a clock field, flashing it when its value changes. Only while the
// widget is not running: a flash every second would be a strobe, and it is the
// single click of a step that is easy to miss.
function setClockField(w, el, text) {
  if (el.textContent === text) return;
  el.textContent = text;
  if (w.running) return;
  bump(el);
}

function renderClock(w) {
  setClockField(w, w.clockTime, `t=${w.time}s`);
  w.clockTime.title = `Step #${stepNumber(w)}`;
  setClockField(w, w.clockBpdu, `${w.bpdus} BPDUs`);
  if (w.settledAt !== null) {
    w.clockConv.textContent = `🌳 ${w.settledAt - w.actionAt}s`;
    w.clockConv.title = "Convergence time";
  } else if (!w.bpdus) {
    w.clockConv.replaceChildren(); // nothing has been sent yet
    w.clockConv.title = "";
  } else if (!w.clockConv.firstElementChild) {
    w.clockConv.replaceChildren(h("i", { class: "mstp-wait", text: "⏳" }));
    w.clockConv.title = "Convergence in progress";
  }
}

function render(w) {
  const snap = snapshot(w);
  const live = !!w.mstp;
  renderClock(w);
  updateBackBtn(w);
  w.svg.replaceChildren();

  const defs = svgEl("defs", {}, w.svg);
  const gray = svgEl("filter", { id: "mstp-gray" }, defs);
  svgEl("feColorMatrix", { type: "saturate", values: "0" }, gray);

  const gEdges = svgEl("g", {}, w.svg);
  const gNodes = svgEl("g", {}, w.svg);

  // Parallel links between the same pair of bridges share a straight line, so
  // fan them out perpendicular to it to keep each visible and separately
  // clickable.
  const pairKey = (e) =>
    e.a.name < e.b.name
      ? `${e.a.name}\0${e.b.name}`
      : `${e.b.name}\0${e.a.name}`;
  const groups = new Map();
  for (const e of w.links) {
    const k = pairKey(e);
    (groups.get(k) || groups.set(k, []).get(k)).push(e);
  }

  for (const e of w.links) {
    const pa = snap.ports.get(e.aPort?.handle);
    const pb = snap.ports.get(e.bPort?.handle);
    const active = live && forwards(e.a, pa) && forwards(e.b, pb);
    const down = live ? isDown(pa) || isDown(pb) : e.link.broken;

    const dx = e.b.x - e.a.x;
    const dy = e.b.y - e.a.y;
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len;
    const uy = dy / len;

    // Perpendicular offset for this link within its parallel group. The sign
    // keys off node names so A--B and B--A land on the same side.
    const group = groups.get(pairKey(e));
    const spread = (group.indexOf(e) - (group.length - 1) / 2) * PARALLEL_GAP;
    const orient = e.a.name < e.b.name ? 1 : -1;
    const ox = -uy * spread * orient;
    const oy = ux * spread * orient;

    // How far from a node's centre the link starts: on the border of its
    // circle, or of its box when it runs no protocol. A parallel link is pushed
    // sideways by (ox, oy), so it leaves the shape at a different place.
    const border = (n, dx, dy) => {
      if (!noStp(n))
        return Math.sqrt(
          Math.max(NODE_RADIUS * NODE_RADIUS - spread * spread, 0),
        );
      const tx = dx ? (Math.sign(dx) * NO_STP_RADIUS - ox) / dx : Infinity;
      const ty = dy ? (Math.sign(dy) * NO_STP_RADIUS - oy) / dy : Infinity;
      return Math.max(0, Math.min(tx, ty));
    };
    const fromA = border(e.a, ux, uy);
    const fromB = border(e.b, -ux, -uy);
    const x1 = e.a.x + ux * fromA + ox;
    const y1 = e.a.y + uy * fromA + oy;
    const x2 = e.b.x - ux * fromB + ox;
    const y2 = e.b.y - uy * fromB + oy;

    e.geom = { x1, y1, x2, y2 };

    if (live) {
      // Larger hit target
      const hit = svgEl(
        "line",
        {
          x1,
          y1,
          x2,
          y2,
          stroke: "transparent",
          "stroke-width": 18,
          "pointer-events": "stroke",
        },
        gEdges,
      );
      hit.style.cursor = "pointer";
      hit.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        if (w.demoOn) return demoClick(w, e);
        // Single click highlights. Double click cuts/restores.
        if (w.lastClick.link === e && ev.timeStamp - w.lastClick.t < 400) {
          w.lastClick = { link: null, t: 0 };
          toggleLink(w, e);
          return;
        }
        w.lastClick = { link: e, t: ev.timeStamp };
        select(w, { type: "link", ref: e });
      });
    }

    svgEl(
      "line",
      {
        x1,
        y1,
        x2,
        y2,
        stroke: !live ? "#888" : down ? "#999" : active ? "#2a7" : "#e55",
        "stroke-width": w.selected?.ref === e ? 5 : active ? 3 : 2,
        "stroke-dasharray": !live || active || down ? "" : "7 5",
        opacity: down ? 0.5 : 1,
        "pointer-events": "none",
      },
      gEdges,
    );

    // The middle of the link, taken between the two port markers. They sit a
    // little inside the line, so the middle of the line itself would be off
    // centre when the two ends are not the same shape.
    const endA = noStp(e.a) ? fromA : PORT_MARKER_OFFSET;
    const endB = noStp(e.b) ? fromB : PORT_MARKER_OFFSET;
    const mx = (e.a.x + ux * endA + (e.b.x - ux * endB)) / 2 + ox;
    const my = (e.a.y + uy * endA + (e.b.y - uy * endB)) / 2 + oy;

    if (down) {
      const s = 7;
      const cross = {
        stroke: "#e55",
        "stroke-width": 3,
        "stroke-linecap": "round",
        "pointer-events": "none",
      };
      svgEl(
        "line",
        { x1: mx - s, y1: my - s, x2: mx + s, y2: my + s, ...cross },
        gEdges,
      );
      svgEl(
        "line",
        { x1: mx - s, y1: my + s, x2: mx + s, y2: my - s, ...cross },
        gEdges,
      );
    }

    if (e.faulty) {
      // A diode at the midpoint.
      const s = 8; // half length along the link
      const wsym = 7; // half width of the base and the bar
      const px = -uy;
      const py = ux;
      const color = !live ? "#888" : down ? "#999" : active ? "#2a7" : "#e55";
      const ax = mx - ux * s; // base (transmitting side)
      const ay = my - uy * s;
      const cx = mx + ux * s; // tip (receiving side)
      const cy = my + uy * s;
      svgEl(
        "polygon",
        {
          points: [
            [ax + px * wsym, ay + py * wsym],
            [ax - px * wsym, ay - py * wsym],
            [cx, cy],
          ]
            .map((p) => p.join(","))
            .join(" "),
          fill: color,
          "pointer-events": "none",
        },
        gEdges,
      );
      svgEl(
        "line",
        {
          x1: cx + px * wsym,
          y1: cy + py * wsym,
          x2: cx - px * wsym,
          y2: cy - py * wsym,
          stroke: color,
          "stroke-width": 3,
          "stroke-linecap": "round",
          "pointer-events": "none",
        },
        gEdges,
      );
    }

    // A port with no protocol has no role or state to show, so it gets no
    // marker.
    if (!w.demoOn && !noStp(e.a)) drawEndpoint(gEdges, e.a, e.b, pa, ox, oy);
    if (!w.demoOn && !noStp(e.b)) drawEndpoint(gEdges, e.b, e.a, pb, ox, oy);
  }

  for (const n of w.nodes) {
    const b = snap.bridges.get(n.bridge?.handle);
    const isRoot = b && b.is_root && !noStp(n);
    const g = svgEl("g", {}, gNodes);
    if (live) g.style.cursor = "pointer";
    const shape = {
      fill: isRoot ? "#2a73" : "#8882",
      stroke: w.selected?.ref === n ? "#06f" : isRoot ? "#2a7" : "#888",
      "stroke-width": w.selected?.ref === n ? 4 : 2,
    };
    // A bridge with no protocol is a box.
    if (noStp(n))
      svgEl(
        "rect",
        {
          x: n.x - NO_STP_RADIUS,
          y: n.y - NO_STP_RADIUS,
          width: 2 * NO_STP_RADIUS,
          height: 2 * NO_STP_RADIUS,
          rx: 3,
          ...shape,
        },
        g,
      );
    else svgEl("circle", { cx: n.x, cy: n.y, r: NODE_RADIUS, ...shape }, g);
    drawNodeGlyph(g, n);
    // The second line names the root the node has elected. The root itself has
    // nothing to point to, so its name takes the whole circle.
    const solo = noStp(n) || w.demoOn;
    const sub = solo || isRoot || !b ? "" : rootName(w, snap, b);
    svgEl(
      "text",
      {
        x: n.x,
        y: sub ? n.y - 1 : n.y + 4,
        "text-anchor": "middle",
        "font-weight": 600,
        "font-size": 13,
      },
      g,
    ).textContent = n.name;
    if (sub)
      svgEl(
        "text",
        {
          x: n.x,
          y: n.y + 12,
          "text-anchor": "middle",
          "font-size": 10,
        },
        g,
      ).textContent = sub;
    if (live)
      g.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        select(w, { type: "node", ref: n });
      });
  }
}

// A faint background glyph sitting behind the node's labels. Either the user's
// icon character (desaturated and faded so the labels stay legible) or, by
// default, the switch symbol.
function drawNodeGlyph(parent, n) {
  if (n.icon) {
    svgEl(
      "text",
      {
        x: n.x,
        y: n.y,
        "text-anchor": "middle",
        "dominant-baseline": "central",
        "font-size": noStp(n) ? (30 * NO_STP_RADIUS) / NODE_RADIUS : 30,
        opacity: 0.3,
        filter: "url(#mstp-gray)",
        "pointer-events": "none",
      },
      parent,
    ).textContent = n.icon;
    return;
  }
  if (noStp(n)) return;
  // Draw a switch symbol otherwise.
  const g = svgEl(
    "g",
    {
      stroke: "#888",
      "stroke-width": 2,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      fill: "none",
      opacity: 0.3,
      "pointer-events": "none",
    },
    parent,
  );
  const edge = 13; // half the total glyph width
  const head = 4; // arrowhead size
  // Two interleaved pairs of arrows. Each arrow spans half the width: tails
  // meet at the centre and the tips point outward, the rightward pair on the
  // right half and the leftward pair on the left half.
  [-9, -3, 3, 9].forEach((dy, i) => {
    const right = i % 2 === 0;
    const y = n.y + dy;
    const tail = n.x;
    const tip = n.x + (right ? edge : -edge);
    const dir = right ? -1 : 1;
    svgEl("line", { x1: tail, y1: y, x2: tip, y2: y }, g);
    svgEl(
      "polyline",
      {
        points: `${tip + dir * head},${y - head} ${tip},${y} ${tip + dir * head},${y + head}`,
      },
      g,
    );
  });
}

// Disabled and Designated both start with "D", so mark disabled ports with "X".
const roleLetter = (role) => (role === "Disabled" ? "X" : role[0]);

function drawEndpoint(parent, from, to, ps, ox = 0, oy = 0) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const px = from.x + ux * PORT_MARKER_OFFSET + ox;
  const py = from.y + uy * PORT_MARKER_OFFSET + oy;
  svgEl(
    "rect",
    {
      x: px - 6,
      y: py - 6,
      width: 12,
      height: 12,
      rx: 2,
      fill: colorFor(ps?.state),
      "pointer-events": "none",
    },
    parent,
  );
  const role = ps ? ps.role : "";
  if (role)
    svgEl(
      "text",
      {
        x: px,
        y: py + 3,
        "text-anchor": "middle",
        "font-size": 8,
        fill: "#fff",
        "font-weight": 700,
        "pointer-events": "none",
      },
      parent,
    ).textContent = roleLetter(role);
}

// -- details panel --------------------------------------------------

function select(w, sel) {
  w.selected = sel;
  render(w);
  renderPanel(w);
}

// Cutting a cable takes down whatever is on it: the core drops the frames it had
// queued there, so their pills go too.
function applyToggle(w, e) {
  if (e.oneway) {
    // Specific case for a one way link, we toggle the faulty state.
    e.faulty = !e.faulty;
    if (e.faulty) w.mstp.linkOneWay(e.aPort, e.bPort);
    else w.mstp.link(e.aPort, e.bPort);
  } else {
    e.link.toggle();
    w.flights = w.flights.filter((f) => f.link !== e);
    emitWave(w, w.wave ? w.wave.gen : 0);
  }
  markAction(w);
}

function toggleLink(w, e) {
  record(w, "toggle", w.links.indexOf(e));
  applyToggle(w, e);
  select(w, { type: "link", ref: e });
}

function renderPanel(w) {
  if (w.demoOn) return;
  const panel = w.panel;
  panel.replaceChildren();
  const snap = snapshot(w);

  if (!w.selected) {
    panel.appendChild(h("h3", { text: "Global timers" }));
    const b0 = snap.topo.bridges[0];
    const protos = protocolsUsed(w);
    // Hops are an MSTP notion. Inside a region MSTP counts hops instead of
    // ageing BPDUs, and every MSTP bridge here joins the same region, so max age
    // only matters when some bridge speaks STP or RSTP.
    const hasMstp = protos.has("mstp");
    const oneRegion = hasMstp && protos.size === 1;
    const rows = [["protocol", w.model.directives.protocol.toUpperCase()]];
    if (b0) {
      rows.push(
        ["hello time", `${b0.hello_time} s`],
        ["forward delay", `${b0.forward_delay} s`],
      );
      if (!oneRegion) rows.push(["max age", `${b0.max_age} s`]);
      if (hasMstp) rows.push(["max hops", b0.max_hops]);
      rows.push(["tx hold count", b0.tx_hold_count]);
    }
    panel.appendChild(kvTable(rows));
    if (w.mstp) panel.appendChild(pcapButton(w, "bpdus.pcap"));
    panel.appendChild(
      h("p", {
        class: "mstp-hint",
        text: "Click a bridge or link for details. Double-click a link to cut or restore it.",
      }),
    );
    return;
  }

  if (w.selected.type === "link") {
    const e = w.selected.ref;
    const pa = shown(e.a, snap.ports.get(e.aPort.handle));
    const pb = shown(e.b, snap.ports.get(e.bPort.handle));
    const broken = e.link.broken;
    const head = h("h3", {
      text: `Link ${e.a.name} ${e.faulty ? "→" : "–"} ${e.b.name} `,
    });
    if (e.faulty) head.appendChild(badge("ONE-WAY", "#d90"));
    else if (broken) head.appendChild(badge("CUT", "#e55"));
    panel.appendChild(head);
    // Both ends of a cable have the same cost, so take it from whichever of them
    // runs the protocol.
    const known = pa || pb;
    panel.appendChild(
      kvTable([
        [
          "cost",
          e.cost != null
            ? e.cost
            : `auto (${known ? known.external_path_cost : "?"})`,
        ],
      ]),
    );
    panel.appendChild(
      portsTable(w, snap, [
        {
          port: e.aPort,
          ps: pa,
          label: e.a.name,
          rapid: isRapid(e.a),
        },
        {
          port: e.bPort,
          ps: pb,
          label: e.b.name,
          rapid: isRapid(e.b),
        },
      ]),
    );
    panel.appendChild(
      h("button", {
        class:
          "mstp-btn mstp-toggle" +
          ((e.oneway ? e.faulty : broken) ? " mstp-active" : ""),
        title: e.oneway
          ? e.faulty
            ? `Let ${e.b.name} send again`
            : `Keep ${e.b.name} receiving, but stop it from sending`
          : broken
            ? "Bring the link back up"
            : "Take the link down",
        html: e.oneway
          ? `<span>${icon("✂️")}Break one way</span>` +
            `<span>${icon("🔗")}Repair link</span>`
          : `<span>${icon("✂️")}Cut link</span>` +
            `<span>${icon("🔗")}Restore link</span>`,
        onclick: () => toggleLink(w, e),
      }),
    );
    if (w.mstp && e.aPort)
      panel.appendChild(pcapButton(w, `${e.a.name}-${e.b.name}.pcap`, e.aPort));
    panel.appendChild(
      h("p", {
        class: "mstp-hint",
        text: !e.oneway
          ? "Double-click a link to cut it."
          : e.faulty
            ? `A one-way fault: ${e.b.name} receives but never sends. ` +
              "Double-click the link to repair it."
            : `Double-click the link to stop ${e.b.name} from sending.`,
      }),
    );
    return;
  }

  // node
  const n = w.selected.ref;
  const b = snap.bridges.get(n.bridge.handle);
  const head = h("h3", { text: n.name + " " });
  if (b && b.is_root && !noStp(n)) head.appendChild(badge("ROOT", "#2a7"));
  if (noStp(n)) head.appendChild(badge("NO STP", "#888"));
  panel.appendChild(head);
  if (b && noStp(n)) panel.appendChild(kvTable([["protocol", "none"]]));
  else if (b)
    panel.appendChild(
      kvTable([
        ["priority", n.prio ?? 32768],
        ["bridge id", b.bridge_id],
        ["root", namedBridgeId(w, snap, b.designated_root)],
        ["cost to root", b.root_path_cost],
        ["protocol", b.protocol_version.toUpperCase()],
      ]),
    );

  const entries = n.ports.map((port) => ({
    port,
    ps: shown(n, snap.ports.get(port.handle)),
    label: peerLabel(w, port, n),
    rapid: isRapid(n),
  }));
  panel.appendChild(portsTable(w, snap, entries));
}

// A bridge whose protocol makes the rapid transitions and handshake happen.
const isRapid = (node) => node.protocol === "rstp" || node.protocol === "mstp";

// The port table shown in both the node and link panels: a "port" / "role /
// state" grid where each row folds out its flag and state details. Each entry
// is { port, ps, label, rapid }. ps is null for a port with no role to show.
function portsTable(w, snap, entries) {
  const tbl = h("table", { class: "mstp-ports" });
  const detailed = entries.filter((e) => e.ps);
  const allOpen =
    detailed.length > 0 && detailed.every((e) => w.flagsOpen.has(e.port.name));

  const hcell = h(
    "div",
    { class: "mstp-rs" },
    h("span", { text: "role / state" }),
  );
  if (detailed.length)
    hcell.appendChild(
      flagsDots(allOpen, () => {
        for (const e of detailed)
          if (allOpen) w.flagsOpen.delete(e.port.name);
          else w.flagsOpen.add(e.port.name);
        renderPanel(w);
      }),
    );
  tbl.appendChild(
    h("thead", {}, h("tr", {}, h("th", { text: "port" }), h("th", {}, hcell))),
  );

  const body = h("tbody");
  for (const { port, ps, label, rapid } of entries) {
    const tr = h("tr");
    tr.appendChild(h("td", { text: label }));
    const cell = h("div", { class: "mstp-rs" });
    const rs = h("span", { text: roleState(w, ps) });
    rs.style.color = colorFor(ps?.state);
    cell.appendChild(rs);
    const open = w.flagsOpen.has(port.name);
    if (ps)
      cell.appendChild(
        flagsDots(open, () => {
          if (open) w.flagsOpen.delete(port.name);
          else w.flagsOpen.add(port.name);
          renderPanel(w);
        }),
      );
    tr.appendChild(h("td", {}, cell));
    body.appendChild(tr);
    if (ps && open) {
      const cont = h(
        "td",
        { class: "mstp-port-detail-cell" },
        kvTable(portDetails(w, snap, ps, rapid)),
      );
      cont.colSpan = 2;
      body.appendChild(h("tr", { class: "mstp-port-detail" }, cont));
    }
  }
  tbl.appendChild(body);
  return tbl;
}

// A three-dot toggle that folds a port's flag/state details in and out.
function flagsDots(open, toggle) {
  const b = h("button", {
    class: "mstp-dots" + (open ? " mstp-dots-open" : ""),
    text: "⋯",
    title: open ? "Hide port details" : "Show port details",
  });
  b.type = "button";
  b.addEventListener("pointerdown", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    toggle();
  });
  return b;
}

// A port identifier the way the standard writes it: 0x8002, the priority in the
// first digit and the port number in the last three.
const portId = (id) => `0x${id.toString(16).padStart(4, "0")}`;

// The flags and the rest of the state worth showing for one port, as kvTable
// rows.
function portDetails(w, snap, ps, rapid) {
  const rows = [];
  rows.push(["port id", portId(ps.port_id)]);
  rows.push(["link type", ps.oper_p2p ? "point-to-point" : "shared"]);
  rows.push(["edge", edgeState(ps)]);
  rows.push(["path cost", ps.external_path_cost]);
  rows.push([
    "cost to root",
    ps.designated_external_cost + ps.external_path_cost,
  ]);

  const flags = portFlags(ps, rapid);
  if (flags) rows.push(["flags", flags]);
  const hs = handshake(ps);
  if (hs) rows.push(["handshake", hs]);

  rows.push([
    "designated bridge",
    namedBridgeId(w, snap, ps.designated_bridge),
  ]);
  rows.push(["designated port", portId(ps.designated_port)]);
  return rows;
}

// The RSTP role-transition variables that are set on the port right now.
function handshake(ps) {
  const notes = [];
  if (ps.proposing) notes.push("proposing");
  if (ps.proposed) notes.push("proposed");
  if (ps.agree) notes.push("agree");
  if (ps.agreed) notes.push("agreed");
  if (ps.sync) notes.push("sync");
  if (ps.synced) notes.push("synced");
  if (ps.re_root) notes.push("re-root");
  return notes.join(", ");
}

function edgeState(ps) {
  const cfg = [];
  if (ps.admin_edge) cfg.push("admin");
  if (ps.auto_edge) cfg.push("auto");
  const oper = ps.oper_edge ? "yes" : "no";
  return cfg.length ? `${oper} (${cfg.join(", ")})` : oper;
}

function roleState(w, ps) {
  return ps ? `${ps.role} / ${stateLabel(w, ps.state)}` : "-";
}

function portFlags(ps, rapid) {
  if (!ps) return "";
  const notes = [];
  if (ps.network_port) notes.push("network");
  if (ps.restricted_role) notes.push("root-guard");
  if (ps.restricted_tcn) notes.push("tcn-guard");
  if (ps.bpdu_guard_port)
    notes.push(ps.bpdu_guard_error ? "bpdu-guard tripped" : "bpdu-guard");
  if (rapid && ps.up && !ps.send_rstp) notes.push("STP fallback");
  if (ps.disputed) notes.push("disputed");
  if (ps.ba_inconsistent) notes.push("BA inconsistent");
  return notes.join(", ");
}

function peerLabel(w, port, node) {
  const e = w.links.find((e) => e.aPort === port || e.bPort === port);
  if (!e) return port.name;
  return `→ ${e.a === node ? e.b.name : e.a.name}`;
}

// Each row is [key, value] or [key, value, color] to tint the value cell.
function kvTable(rows) {
  const tbl = h("table", { class: "mstp-kv" });
  const body = h("tbody");
  for (const [k, v, color] of rows) {
    const td = h("td", { text: String(v) });
    if (color) td.style.color = color;
    body.appendChild(h("tr", {}, h("th", { text: k }), td));
  }
  tbl.appendChild(body);
  return tbl;
}

function badge(text, color) {
  const b = h("span", { class: "mstp-badge", text });
  b.style.background = color;
  return b;
}

// The BPDUs the core has transmitted but whose pills have not set off yet, one
// count per port. They are on the wire and the capture holds them, but they are
// not part of what has been played, so the pcap leaves them out.
function notLaunched(w) {
  const n = new Map();
  for (const f of w.flights)
    if (f.start >= w.clock) n.set(f.src, (n.get(f.src) || 0) + 1);
  return n;
}

// A button that saves captured BPDUs as a pcap: the whole capture when no port
// is given, or just that port's link (both directions) when one is.
function pcapButton(w, filename, port) {
  return h("button", {
    class: "mstp-btn mstp-pcap",
    title: `Save the BPDUs seen so far as ${filename}`,
    html: `${icon("📦")}Download packets`,
    onclick: () => w.mstp.downloadPcap(port, filename, notLaunched(w)),
  });
}

// -- control links --------------------------------------------------
//
// A regular <a href="#mstp:OP,OP,..."> link anywhere in the page puts the
// nearest topology in a given state: a click resets it, then applies each op
// in turn, without animation. An op is either:
//
//   N     play N steps, as the Step button would
//   A--B  toggle the link between bridges A and B; with several links
//         between the two, A--B:2 picks the second, in definition order
//   A->B  put a red arrow on the BPDUs A sends to B, so they can be told apart
//         from the others crossing the diagram; the link is picked as above,
//         and A->B#2 takes only the second BPDU the port sends in the step
//   ...   leave the clock running at the end, as the Start button would
//   @     turn slow motion on, as the snail box would; without it the box is
//         left as the reader set it, so @,... plays the end in slow motion
//
// So #mstp:B--C,30 restarts the topology, cuts the link B -- C and plays 30
// steps. Only the last step is animated, so that is where an arrow shows:
// #mstp:B--C,30,B->D marks what B sends to D there, and goes on marking it if
// the widget is stepped on. An arrow, ... and @ do not move the sim on, so they
// can sit anywhere in the list.

// Host element -> widget: where mount() files a widget, and where the control
// links and the sticky code find it back.
const widgets = new WeakMap();

const { copySeekLink } = (() => {
  // The topology a control link drives: the closest one before the link.
  function closestWidget(from) {
    let before = null;
    for (const host of document.querySelectorAll(".mstp-host")) {
      if (from.compareDocumentPosition(host) & Node.DOCUMENT_POSITION_PRECEDING)
        before = host;
    }
    return before && widgets.get(before);
  }

  const SEEK_TOGGLE = /^(.+?)\s*--\s*(.+?)(?:\s*:(\d+))?$/;
  const SEEK_ARROW = /^(.+?)\s*->\s*(.+?)(?:\s*:(\d+))?(?:\s*#(\d+))?$/;
  const SEEK_RUN = "...";
  const SEEK_SNAIL = "@";

  // The link an op names, as an index into w.links, or -1. nth picks one when
  // several links join the same two bridges.
  function pickLink(w, a, b, nth) {
    const matching = w.links
      .map((l, i) => i)
      .filter(
        (i) =>
          (w.links[i].a.name === a && w.links[i].b.name === b) ||
          (w.links[i].a.name === b && w.links[i].b.name === a),
      );
    return matching[(nth ? +nth : 1) - 1] ?? -1;
  }

  // Reset a topology and apply a #mstp: op list to it.
  function seek(w, spec) {
    if (!w.mstp || w.editing || w.demoOn) return;
    setRunning(w, false);
    // Where the widget stands now, to tell later which way the seek went, and the
    // diagram to slide out on the way there.
    const from = historyPos(w);
    const ghost = snapshotCanvas(w);
    // Keep the selected bridge or link selected across the rebuild.
    const selected = w.selected;
    const sel =
      selected &&
      (selected.type === "link"
        ? { type: "link", index: w.links.indexOf(selected.ref) }
        : { type: "node", name: selected.ref.name });
    build(w);
    const all = spec
      .split(",")
      .map((tok) => tok.trim())
      .filter(Boolean);
    // The arrows are set aside: they mark BPDUs instead of moving the sim on, so
    // they are taken first and their place in the list does not matter. Same for
    // the ask to go on playing, which only matters once the rest is done.
    const arrows = all.filter((op) => SEEK_ARROW.test(op));
    const keepPlaying = all.includes(SEEK_RUN);
    const ops = all.filter(
      (op) => op !== SEEK_RUN && op !== SEEK_SNAIL && !SEEK_ARROW.test(op),
    );
    // Only the snail op says anything about slow motion: without it the box stays
    // as the reader set it.
    if (all.includes(SEEK_SNAIL)) setSlow(w, true);

    for (const op of arrows) {
      const m = op.match(SEEK_ARROW);
      const e = w.links[pickLink(w, m[1], m[2], m[3])];
      const port = e && (e.a.name === m[1] ? e.aPort : e.bPort);
      if (!port) {
        console.warn(`mstp: cannot apply "${op}"`);
        continue;
      }
      w.highlight.push({ src: port.handle, nth: m[4] ? +m[4] - 1 : null });
    }

    // When the list ends on a step count, its final step plays animated.
    const playLast = ops.length > 0 && /^\d+$/.test(ops[ops.length - 1]);

    ops.forEach((op, oi) => {
      if (/^\d+$/.test(op)) {
        let n = +op;
        if (playLast && oi === ops.length - 1) n -= 1; // hold the last one back
        for (let i = 0; i < n; i++) applyStep(w);
        return;
      }
      const m = op.match(SEEK_TOGGLE);
      const idx = m ? pickLink(w, m[1], m[2], m[3]) : -1;
      if (idx < 0) {
        console.warn(`mstp: cannot apply "${op}"`);
        return;
      }
      record(w, "toggle", idx);
      applyOp(w, { t: "toggle", link: idx });
    });
    select(
      w,
      sel &&
        (sel.type === "link"
          ? { type: "link", ref: w.links[sel.index] }
          : { type: "node", ref: w.nodes.find((n) => n.name === sel.name) }),
    );
    // The step held back counts too, it is about to play.
    const to = historyPos(w) + (playLast ? 1 : 0);
    if (to !== from && to !== from + 1) animateSlide(w, ghost, to < from);
    if (playLast) stepOnce(w);
    if (keepPlaying) setRunning(w, true);
  }

  // Where a link sits among those joining the same two bridges, the way pickLink
  // counts them. Empty when it is the only one: the op needs no number then.
  function linkNth(w, e) {
    const same = w.links.filter(
      (l) =>
        (l.a.name === e.a.name && l.b.name === e.b.name) ||
        (l.a.name === e.b.name && l.b.name === e.a.name),
    );
    return same.length > 1 ? `:${same.indexOf(e) + 1}` : "";
  }

  // The op list that leads to the state on show: the cuts and restores of the
  // history with the step counts between them.
  function seekOps(w) {
    const ops = [];
    let steps = 0;
    const flush = () => {
      if (steps) ops.push(String(steps));
      steps = 0;
    };
    for (let i = 0; i < w.cursor; i++) {
      const op = w.history[i];
      if (op.t === "toggle") {
        flush();
        const e = w.links[op.link];
        ops.push(`${e.a.name}--${e.b.name}${linkNth(w, e)}`);
      } else if (op.t === "tick" || w.history[i - 1]?.t !== "tick") {
        steps += 1; // a deliver landing a tick's wave is part of that same step
      }
    }
    flush();
    return ops;
  }

  // Put the link that plays the current state back on the clipboard, and flash
  // the clock to say it has been taken.
  function copySeekLink(w, el) {
    if (!w.mstp || w.editing) return;
    const link = `#mstp:${seekOps(w).join(",")}`;
    navigator.clipboard?.writeText(link).then(
      () => bump(el, "mstp-bump-copy"),
      (err) => console.warn(`mstp: cannot copy "${link}" (${err})`),
    );
  }

  document.addEventListener("click", (ev) => {
    const a = ev.target.closest?.("a[href^='#mstp:']");
    if (!a) return;
    ev.preventDefault();
    const w = closestWidget(a);
    if (!w) return;
    seek(w, decodeURIComponent(a.hash.slice(6)));
  });

  return { copySeekLink };
})();

// -- konami code ----------------------------------------------------

(() => {
  const CODE = [
    "ArrowUp",
    "ArrowUp",
    "ArrowDown",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "ArrowLeft",
    "ArrowRight",
    "b",
    "a",
  ];
  let at = 0;

  document.addEventListener("keydown", (ev) => {
    const key = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
    // A key out of order starts the code over, and may be its first one.
    at = key === CODE[at] ? at + 1 : key === CODE[0] ? 1 : 0;
    if (at < CODE.length) return;
    at = 0;
    for (const host of document.querySelectorAll(".mstp-host")) {
      const w = widgets.get(host);
      if (w) startDemo(w);
    }
  });
})();

// -- bootstrap ------------------------------------------------------

const SELECTOR = "pre.mstp-topology, div.mstp-topology:has(> pre > code)";

function mountAll(scope = document) {
  for (const el of scope.querySelectorAll(SELECTOR)) mount(el);
  scheduleSticky();
}

if (document.readyState === "loading")
  document.addEventListener("DOMContentLoaded", () => mountAll());
else mountAll();
