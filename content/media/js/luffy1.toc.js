/* Highlight side TOC entries whose section is visible. */
luffy.do(() => {
  const toc = document.querySelector(".lf-main .toc");
  if (!window.ResizeObserver || !toc) return;

  /* Build a list of entries. Each entry contains a Hx element (heading) and
     the matching A element in TOC (link). */
  const entries = [];
  for (const link of toc.querySelectorAll("li > a")) {
    const id = decodeURIComponent(link.getAttribute("href").slice(1));
    const heading = id && document.getElementById(id);
    if (heading) entries.push({ heading, link });
  }
  if (!entries.length) return;

  /* Toggle lf-toc-active class for each element in the TOC. */
  const scrollEl = toc.querySelector("ul");
  let scrolledTo = null;
  const apply = () => {
    const tops = entries.map((e) => e.heading.getBoundingClientRect().top);
    let lastActive = null;
    for (let i = 0; i < entries.length; i++) {
      const end = i + 1 < entries.length ? tops[i + 1] : Infinity;
      const active = tops[i] < innerHeight && end > 0;
      entries[i].link.classList.toggle("lf-toc-active", active);
      if (active) lastActive = entries[i].link;
    }
    if (lastActive && lastActive !== scrolledTo) {
      scrolledTo = lastActive;
      const elTop =
        lastActive.getBoundingClientRect().top -
        scrollEl.getBoundingClientRect().top +
        scrollEl.scrollTop;
      scrollEl.scrollTop = elTop - (scrollEl.clientHeight * 2) / 3;
    }
  };

  /* Throttle updates to once every 500ms. */
  let pending = false;
  const schedule = () => {
    if (pending) return;
    pending = true;
    setTimeout(() => {
      pending = false;
      apply();
    }, 500);
  };

  new ResizeObserver(schedule).observe(document.body);
  addEventListener("scroll", schedule, { passive: true });
});
