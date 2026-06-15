/* Some browsers support CSS anchor positioning but compute anchored sidenote
   positions incorrectly, leaving them stacked on top of each other. Notably
   Safari 26.x with x < 5. Detect such overlaps and fall back to inline
   sidenotes when they happen. */

luffy.do(() => {
  const main = document.querySelector(".lf-main");
  if (!main || !CSS.supports("anchor-name: --a")) return;
  const notes = [...main.querySelectorAll(".lf-sidenote")];
  if (notes.length < 2) return;

  const check = () => {
    /* Wait for sidenotes to be in the margin. Then check if they are
       overlapping and toggle lf-sidenotes-overlap class in this case. */
    if (getComputedStyle(notes[0]).position !== "absolute") return;
    ro.disconnect();
    const rects = notes
      .map((n) => n.getBoundingClientRect())
      .sort((a, b) => a.top - b.top);
    const overlap = rects.some((r, i) => i && r.top < rects[i - 1].bottom);
    if (overlap) {
      console.info("Apply workaround for overlapping sidenotes");
      main.classList.add("lf-sidenotes-overlap");
      luffy.count?.({
        event: "sidenote-collision",
        title: "Workaround for sidenote collision",
      });
    }
  };

  const ro = new ResizeObserver(check);
  ro.observe(main);
});
