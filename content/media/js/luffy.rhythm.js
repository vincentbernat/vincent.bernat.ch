/* Keep vertical rhythm around media. One day, this could be done with CSS
   Rhythmic Sizing Module Level 1: https://www.w3.org/TR/css-rhythm-1/ */

luffy.do(() => {
  if (!window.ResizeObserver) return;
  const targets = document.querySelectorAll(".lf-media-outer, .lf-gallery");
  if (!targets.length) return;

  const heights = new Map();
  const getRlh = () =>
    parseFloat(getComputedStyle(document.documentElement).lineHeight);
  let lastRlh = 0;

  const adjust = (el, height) => {
    if (!lastRlh) lastRlh = getRlh();
    const minPad = el.matches("figure > .lf-media-outer") ? lastRlh / 4 : 0;
    const padding = Math.ceil((height + minPad) / lastRlh) * lastRlh - height;
    el.style.padding = `${padding / 2}px 0`;
  };

  /* React to the change of dimension of a media element. */
  const ro = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const height = entry.contentBoxSize[0].blockSize;
      heights.set(entry.target, height);
      adjust(entry.target, height);
    }
  });
  for (const target of targets) {
    ro.observe(target);
  }

  /* React to the potential change of root line height. */
  new ResizeObserver(() => {
    const rlh = getRlh();
    if (rlh === lastRlh) return;
    lastRlh = rlh;
    for (const [el, height] of heights) {
      adjust(el, height);
    }
  }).observe(document.documentElement);
});
