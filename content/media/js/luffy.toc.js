/* Highlight side TOC entries based on the position of their target heading. A
   link is lf-toc-active from the moment its heading is in the viewport until
   the next heading at the same or shallower TOC depth has scrolled above. Then,
   the class lf-toc-past applies. */
luffy.do(() => {
  const toc = document.querySelector(".lf-main .toc");
  if (!window.IntersectionObserver || !window.ResizeObserver || !toc) return;

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
      p && p !== toc;
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

  /* Compute the current state of a heading from its geometry. */
  const stateOf = (heading) => {
    const rect = heading.getBoundingClientRect();
    return rect.bottom <= 0
      ? "above"
      : rect.top >= innerHeight
        ? "below"
        : "in";
  };

  /* Update the classes for each element in the TOC. */
  const apply = () => {
    const states = entries.map((e) => stateOf(e.heading));
    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      const term = e.terminator >= 0 ? states[e.terminator] : null;
      const past = states[i] === "above" && term === "above";
      const active = states[i] === "in" || (states[i] === "above" && !past);
      e.link.classList.toggle("lf-toc-active", active);
      e.link.classList.toggle("lf-toc-past", past);
      e.link.classList.toggle("lf-toc-future", !past && !active);
    }
  };

  const io = new IntersectionObserver(apply);
  const ro = new ResizeObserver(apply);
  for (const e of entries) io.observe(e.heading);
  ro.observe(document.body);
});
