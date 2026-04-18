/* Keyboard shortcuts and back to top */

luffy.do(() => {
  document
    .querySelector(".lf-backtotop a")
    ?.addEventListener("click", (event) => {
      window.scrollTo(0);
      event.preventDefault();
    });

  // For search
  const searchForm =
    document.querySelector("#lf-search-query") ||
    document.querySelector("#lf-search-input");

  // For grid
  const baselineOffset = getComputedStyle(document.documentElement)
    .getPropertyValue("--lf-baseline-offset")
    .trim();
  let gridState = 0;

  document.addEventListener("keydown", (event) => {
    if (
      event.ctrlKey &&
      !event.altKey &&
      !event.shiftKey &&
      !event.metaKey &&
      event.key === "k"
    ) {
      // Focus the search form.
      if (document.activeElement !== searchForm) {
        searchForm.focus();
        event.preventDefault();
      }
    }
    if (
      event.ctrlKey &&
      event.altKey &&
      !event.shiftKey &&
      !event.metaKey &&
      event.key === "g"
    ) {
      // Ctrl+Alt+G: cycle debug grid (off → grid → grid on baseline → off).
      // --lf-baseline-offset is precomputed at build time in :root.
      gridState = (gridState + 1) % 3;
      document.body.classList.toggle("lf-debug-grid", gridState > 0);
      document.documentElement.style.setProperty(
        "--lf-baseline-offset",
        gridState === 2 ? baselineOffset : "0",
      );
      event.preventDefault();
    }
  });
});
