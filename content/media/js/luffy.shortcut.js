/* Keyboard shortcuts */

luffy.do(() => {
  // For search
  const searchForm =
    document.querySelector("#lf-search-query") ||
    document.querySelector("#lf-search-input");

  // For grid
  let gridState = 0;

  document.addEventListener("keydown", (event) => {
    if (
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
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
      !event.altKey &&
      event.shiftKey &&
      !event.metaKey &&
      event.key === "G"
    ) {
      // Ctrl+Alt+G: cycle debug grid (off → grid → grid on baseline → off).
      // --lf-baseline-offset is precomputed at build time in :root.
      gridState = (gridState + 1) % 3;
      document.documentElement.classList.toggle(
        "lf-debug-grid-1",
        gridState === 1,
      );
      document.documentElement.classList.toggle(
        "lf-debug-grid-2",
        gridState === 2,
      );
      event.preventDefault();
    }
  });
});
