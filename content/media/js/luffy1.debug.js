/* Debug tools. Each key is the letter typed after ←, ←. */

let gridState = 0;

luffy.debug = {
  g() {
    // Cycle debug grid (off → grid → grid on baseline → off).
    // --lf-baseline-offset is precomputed at build time in :root.
    gridState = (gridState + 1) % 3;
    const classes = document.documentElement.classList;
    classes.toggle("lf-debug-grid-1", gridState === 1);
    classes.toggle("lf-debug-grid-2", gridState === 2);
  },
};
