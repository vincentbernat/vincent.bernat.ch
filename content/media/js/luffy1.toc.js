/* Highlight side TOC entries based on the position of their target heading. A
   link is lf-toc-active from the moment its heading is in the viewport until
   the next heading at the same or shallower TOC depth has scrolled above. Then,
   the class lf-toc-past applies. */
luffy.do(() => {
  const toc = document.querySelector(".lf-main .toc");
  if (!window.ResizeObserver || !toc) return;

  /* Build a list of entries. Each entry contains a Hx element (heading), the
     matching A element in TOC (link), the depth of this TOC entry, and the
     index of the heading element that would make this element "inactive"
     (terminator). */
  const entries = [];
  for (const link of toc.querySelectorAll("li > a")) {
    const id = decodeURIComponent(link.getAttribute("href").slice(1));
    const heading = id && document.getElementById(id);
    if (!heading) continue;
    let depth = 0;
    for (
      let p = link.parentElement.parentElement;
      p !== toc;
      p = p.parentElement
    ) {
      if (p.tagName === "UL") depth++;
    }
    entries.push({ heading, link, depth, terminator: -1 });
  }
  if (!entries.length) return;

  for (let i = 0; i < entries.length; i++) {
    for (let j = i + 1; j < entries.length; j++) {
      if (entries[j].depth <= entries[i].depth) {
        entries[i].terminator = j;
        break;
      }
    }
  }

  /* Compute the current state of a heading from its top edge: "above" as soon
     as it reaches the top of the viewport (so its predecessor becomes past
     the moment the next section starts). */
  const stateOf = (heading) => {
    const top = heading.getBoundingClientRect().top;
    return top <= 0 ? "above" : top >= innerHeight ? "below" : "in";
  };

  /* Update the classes for each element in the TOC. */
  const scrollEl = toc.firstElementChild;
  const apply = () => {
    const states = entries.map((e) => stateOf(e.heading));
    let lastActive = null;
    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      const term = e.terminator >= 0 ? states[e.terminator] : null;
      const past = states[i] === "above" && term === "above";
      const active = states[i] === "in" || (states[i] === "above" && !past);
      e.link.classList.toggle("lf-toc-active", active);
      e.link.classList.toggle("lf-toc-past", past);
      e.link.classList.toggle("lf-toc-future", !past && !active);
      if (active) lastActive = e.link;
    }
    if (lastActive) {
      const elTop =
        lastActive.getBoundingClientRect().top -
        scrollEl.getBoundingClientRect().top +
        scrollEl.scrollTop;
      scrollEl.scrollTop = elTop - (scrollEl.clientHeight * 2) / 3;
    }
  };

  /* Throttle updates to once per frame update. */
  let pending = false;
  const schedule = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      apply();
    });
  };

  new ResizeObserver(schedule).observe(document.body);
  addEventListener("scroll", schedule, { passive: true });
});
