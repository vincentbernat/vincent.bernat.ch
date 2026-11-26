// Player inlined by svg.mjs in the line-breaking SVG. It shows each
// combination of features for the same duration while the width of the text
// block grows. The page may select a combination or slow it down with
// messages, and it is told the combination shown until one is selected. The
// pointer over the SVG pauses it and, from the narrowest position of the right
// edge, sets the width.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const SHY = "\u00ad";
  const NBSP = "\u00a0";
  const NNBSP = "\u202f";
  // Same values as scratch/typo-harness/page.html: 20px Literata, 1.5 line
  // height, a block starting after a padding of 24 pixels and a label
  const pad = 24;
  const label = 36;
  const lineHeight = 30;
  const top = 0.15; // half-leading
  const baseline = 23.69;
  const ex = 10.14;
  const duration = 3.5; // seconds for each combination
  const hold = 1; // seconds at the narrowest width
  const sweep = 2; // seconds from the narrowest to the widest width
  const loop = 3.25; // loop over one combination before its last frames
  const grow = 0.1;
  const before = 20; // pointer reacting before the narrowest width
  // Same marks as luffy1.debug.js
  const ragMax = 0.15;
  const wideMin = 2;
  const wideMax = 4;

  const strip = (s) => s.split(SHY).join("");
  const create = (parent, name, attributes = {}) => {
    const el = document.createElementNS(NS, name);
    for (const key of Object.keys(attributes))
      el.setAttribute(key, attributes[key]);
    parent.appendChild(el);
    return el;
  };
  const empty = (el) => {
    while (el.firstChild) el.removeChild(el.firstChild);
  };
  const setText = (el, text) => {
    if (el.textContent !== text) el.textContent = text;
  };

  // Draw an animation in an SVG element. Return functions to select a
  // combination and to slow it down. onIndex is called with the combination
  // shown, until one is selected.
  const player = (svg, data, onIndex) => {
    const [from, to] = data.widths;
    const count = data.combos.length;
    const combos = data.combos.map((combo) => {
      let previous = null;
      return {
        ...combo,
        l: combo.l.map((layout) =>
          layout === 0 ? previous : (previous = layout),
        ),
      };
    });
    const features = {
      hyphens: new Set(combos.map((c) => c.h)).size > 1,
      justify: new Set(combos.map((c) => c.j)).size > 1,
      pretty: new Set(combos.map((c) => c.p)).size > 1,
    };

    // Drawn over the first frame, in the row of the animation
    const box = svg.viewBox.baseVal;
    const canvas = create(svg, "g", {
      transform: `translate(0 ${data.row * box.height})`,
    });
    create(canvas, "rect", {
      width: box.width,
      height: box.height,
      class: "lf1-background",
    });
    const caption = create(canvas, "text", {
      x: pad,
      y: pad + 16,
      class: "lf1-caption",
    });
    const text = { class: "lf1-text", visibility: "hidden" };
    const group = create(canvas, "g", {
      transform: `translate(${pad} ${pad + label})`,
    });
    const heads = data.words.map(() => create(group, "text", text));
    const tails = data.words.map(() => create(group, "text", text));
    // Hyphens added by the browser at the end of a line
    const dashes = data.words.map(() => {
      const dash = create(group, "text", text);
      dash.textContent = "-";
      return dash;
    });
    const measurer = create(group, "text", text);
    const marks = create(canvas, "g", {
      transform: `translate(${pad} ${pad + label})`,
    });
    const edge = create(canvas, "rect", {
      y: pad + label - 6,
      width: 1,
      class: "lf1-edge",
    });

    const lengths = new Map();
    const length = (s) => {
      if (!lengths.has(s)) {
        measurer.textContent = s;
        lengths.set(s, measurer.getComputedTextLength());
      }
      return lengths.get(s);
    };
    const spaces = {
      " ": () => length("x x") - length("xx"),
      [NBSP]: () => length(`x${NBSP}x`) - length("xx"),
    };

    // A part of a word takes the width the browser gave it. The browsers
    // were recorded with whole-pixel glyph advances, other renderings would
    // change the spaces between words.
    const put = (el, content, line, x, end) => {
      setText(el, content);
      el.setAttribute("x", x / 10);
      el.setAttribute("y", line * lineHeight + baseline);
      el.setAttribute("textLength", Math.max(0, (end - x) / 10));
      el.removeAttribute("visibility");
    };
    // A part of a word: its line, start, width of its text, end with the
    // hyphen of the browser, and its text with and without soft hyphens. The
    // box of the last character before a break includes the hyphen.
    const fragment = (line, x, end, content, raw, dash) => ({
      line,
      x: x / 10,
      width: (end - x) / 10 - dash,
      end: end / 10,
      text: content,
      raw,
    });
    const place = (layout) =>
      data.words.map((word, i) => {
        const p = layout[i];
        if (p.length === 3) {
          put(heads[i], strip(word), p[0], p[1], p[2]);
          tails[i].setAttribute("visibility", "hidden");
          dashes[i].setAttribute("visibility", "hidden");
          return [fragment(p[0], p[1], p[2], strip(word), word, 0)];
        }
        const k = p[3];
        const first = strip(word.slice(0, k));
        const second = strip(word.slice(k));
        const hyphen = length("-") * 10;
        put(heads[i], first, p[0], p[1], p[2] - hyphen);
        put(tails[i], second, p[4], p[5], p[6]);
        dashes[i].setAttribute("x", (p[2] - hyphen) / 10);
        dashes[i].setAttribute("y", p[0] * lineHeight + baseline);
        dashes[i].removeAttribute("visibility");
        return [
          fragment(p[0], p[1], p[2], first, word.slice(0, k), length("-")),
          fragment(p[4], p[5], p[6], second, word.slice(k), 0),
        ];
      });

    const lineTop = (line) => line * lineHeight + top;
    const bar = (x, line, w, color) =>
      create(marks, "rect", {
        x,
        y: line * lineHeight + baseline - ex,
        width: w,
        height: ex,
        fill: color,
      });
    const drawMarks = (fragments, combo, width) => {
      empty(marks);
      let lines = 0;
      const ends = [];
      for (const parts of fragments) {
        for (const f of parts) {
          lines = Math.max(lines, f.line + 1);
          ends[f.line] = Math.max(ends[f.line] || 0, f.end);
          // Soft hyphens, scaled like the text to its recorded width
          let shown = 0;
          for (const c of f.raw) {
            if (c !== SHY) {
              shown++;
              continue;
            }
            const x =
              f.x + (length(f.text.slice(0, shown)) * f.width) / length(f.text);
            create(marks, "rect", {
              x: x - 0.5,
              y: lineTop(f.line),
              width: 1,
              height: ex,
              class: "lf1-shy",
            });
          }
        }
      }
      // No-break spaces after a word
      data.separators.forEach((s, i) => {
        const f = fragments[i][fragments[i].length - 1];
        const y = lineTop(f.line);
        if (s === NBSP) {
          create(marks, "polygon", {
            points: [
              [f.end - 0.1 * ex, y + 0.2 * ex],
              [f.end + 0.5 * ex, y + 0.2 * ex],
              [f.end + 0.2 * ex, y + 0.8 * ex],
            ].join(" "),
            class: "lf1-nbsp",
          });
        } else if (s === NNBSP) {
          create(marks, "circle", {
            cx: f.end + 0.2 * ex,
            cy: y + 0.5 * ex,
            r: 0.2 * ex,
            class: "lf1-nbsp",
          });
        }
      });
      if (!combo.j) {
        // Rags of lines but the last one
        for (let line = 0; line < lines - 1; line++) {
          const rag = width - ends[line];
          if (rag <= 0) continue;
          const bad = Math.min(rag / (width * ragMax), 1);
          bar(ends[line], line, rag, `hsl(${120 * (1 - bad)} 80% 45%)`);
        }
      } else {
        // Gaps between words of a line, wider than wideMin spaces
        data.separators.forEach((s, i) => {
          if (!(s in spaces)) return;
          const a = fragments[i][fragments[i].length - 1];
          const b = fragments[i + 1][0];
          if (a.line !== b.line) return;
          const space = spaces[s]();
          const gap = b.x - a.end;
          if (gap <= wideMin * space) return;
          const bad = Math.min(
            (gap / space - wideMin) / (wideMax - wideMin),
            1,
          );
          bar(a.end, a.line, gap, `hsl(${60 * (1 - bad)} 90% 50%)`);
        });
      }
      edge.setAttribute("x", pad + width);
      edge.setAttribute("height", lines * lineHeight + 12);
    };

    const drawCaption = (combo, width) => {
      empty(caption);
      const parts = [[data.browser]];
      if (features.hyphens) parts.push([`hyphens: ${combo.h}`, true]);
      if (features.justify) parts.push(["text-align: justify", combo.j]);
      if (features.pretty) parts.push(["text-wrap: pretty", combo.p]);
      parts.push([`${width}px`]);
      parts.forEach(([content, on], i) => {
        if (i) create(caption, "tspan").textContent = " · ";
        const span = create(caption, "tspan");
        span.textContent = content;
        if (on !== undefined)
          span.setAttribute("class", on ? "lf1-on" : "lf1-off");
      });
    };

    let shown = null;
    const render = (index, width) => {
      const key = `${index}:${width}`;
      if (key === shown) return;
      shown = key;
      const combo = combos[index];
      drawMarks(place(combo.l[width - from]), combo, width);
      drawCaption(combo, width);
    };

    // Until a combination is selected, play all of them
    let all = true;
    let index = 0;
    let time = 0;
    let speed = 1;
    let hovering = false;
    let pointed = null;
    let last = null;
    let visible = true;
    const widthAt = (local) => {
      const x = Math.min(1, Math.max(0, (local - hold) / sweep));
      return Math.round(from * (1 + grow * x * x * (3 - 2 * x)));
    };
    const tick = (now) => {
      const dt = last === null ? 0 : (now - last) / 1000;
      last = now;
      if (!hovering && visible) {
        time += dt * speed;
        if (all) {
          time %= count * duration;
          const i = Math.floor(time / duration);
          if (i !== index) {
            index = i;
            onIndex(index);
          }
        } else if (time >= loop) {
          time = 0;
        }
      }
      const local = all ? time - index * duration : time;
      const width = pointed !== null ? pointed : widthAt(local);
      if (visible) render(index, Math.min(to, Math.max(from, width)));
      requestAnimationFrame(tick);
    };
    if ("IntersectionObserver" in window)
      new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
      }).observe(svg);

    svg.addEventListener("mouseenter", () => (hovering = true));
    svg.addEventListener("mousemove", (event) => {
      hovering = true;
      // The SVG may be shrunk, use the position as a part of its width
      const rect = svg.getBoundingClientRect();
      const x =
        ((event.clientX - rect.left) * svg.viewBox.baseVal.width) / rect.width;
      if (x - pad >= from - before) pointed = Math.round(x - pad);
    });
    svg.addEventListener("mouseleave", () => {
      hovering = false;
      if (pointed !== null) {
        // Continue from the frame shown, the inverse of the smoothstep
        const y = Math.min(
          1,
          Math.max(0, (Math.min(to, pointed) / from - 1) / grow),
        );
        const local = hold + sweep * (0.5 - Math.sin(Math.asin(1 - 2 * y) / 3));
        time = all ? index * duration + local : local;
      }
      pointed = null;
    });

    onIndex(index);
    requestAnimationFrame(tick);
    return {
      features,
      select(i) {
        all = false;
        index = i;
        time = 0;
      },
      slow(on) {
        speed = on ? 0.5 : 1;
      },
    };
  };

  // The fragment of the URL selects the animation, the first one by default
  const animations = JSON.parse(document.getElementById("data").textContent);
  const data =
    animations[location.hash.slice(1)] ||
    animations[Object.keys(animations)[0]];
  const parent = window.parent !== window ? window.parent : null;
  const animation = player(document.documentElement, data, (index) => {
    if (parent) parent.postMessage({ lf1LineBreak: { index } }, "*");
  });
  window.addEventListener("message", (event) => {
    if (event.source !== parent) return;
    const message = event.data && event.data.lf1LineBreak;
    if (!message) return;
    const index = message.index;
    if (Number.isInteger(index) && index >= 0 && index < data.combos.length)
      animation.select(index);
    if (typeof message.slow === "boolean") animation.slow(message.slow);
  });
})();
