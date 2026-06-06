/* Some browsers support CSS anchor positioning but compute anchored sidenote
   positions incorrectly, leaving them stacked on top of each other. Notably
   Safari 26.x with x < 5. Detect such overlaps and fall back to inline
   sidenotes when they happen. */

luffy.do(() => {
  const main = document.querySelector(".lf-main");
  const notes = [...main.querySelectorAll(".lf-sidenote")];
  if (!main || !CSS.supports("anchor-name: --a") || notes.length < 2) return;

  const check = () => {
    /* Wait for sidenotes to be in the margin. Then check if they are
       overlapping and toggle lf-sidenotes-overlap class in this case. */
    if (getComputedStyle(notes[0]).position !== "absolute") return;
    ro.disconnect();
    const rects = notes
      .map((n) => n.getBoundingClientRect())
      .sort((a, b) => a.top - b.top);
    for (let i = 1; i < rects.length; i++) {
      if (rects[i].top < rects[i - 1].bottom) {
        console.info("Apply workaround for overlapping sidenotes");
        main.classList.add("lf-sidenotes-overlap");
        return;
      }
    }
  };

  const ro = new ResizeObserver(check);
  ro.observe(main);
});
