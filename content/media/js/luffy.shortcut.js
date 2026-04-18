/* Keyboard shortcuts and back to top */

luffy.do(() => {
  document
    .querySelector(".lf-backtotop a")
    ?.addEventListener("click", (event) => {
      window.scrollTo(0);
      event.preventDefault();
    });

  const searchForm =
    document.querySelector("#lf-search-query") ||
    document.querySelector("#lf-search-input");
  document.addEventListener("keydown", (event) => {
    if (
      event.ctrlKey &&
      !event.altKey &&
      !event.shiftKey &&
      !event.metaKey &&
      event.key === "k"
    ) {
      if (document.activeElement !== searchForm) {
        searchForm.focus();
        event.preventDefault();
      }
    }
    // Ctrl+Alt+G: cycle debug grid (off → grid → grid on baseline → off).
    // --lf-baseline-offset drives the offset: unset = no offset, computed = baseline.
    if (
      event.ctrlKey &&
      event.altKey &&
      !event.shiftKey &&
      !event.metaKey &&
      event.key === "g"
    ) {
      const root = document.documentElement;
      const offset = root.style.getPropertyValue("--lf-baseline-offset");
      if (!document.body.classList.contains("lf-debug-grid")) {
        document.body.classList.add("lf-debug-grid");
      } else if (!offset) {
        const ctx = document.createElement("canvas").getContext("2d");
        ctx.font = `100px ${getComputedStyle(root).fontFamily}`;
        const m = ctx.measureText("A");
        const baseline =
          ((150 - m.fontBoundingBoxAscent - m.fontBoundingBoxDescent) / 2 +
            m.fontBoundingBoxAscent) /
          150;
        root.style.setProperty("--lf-baseline-offset", `${baseline}rlh`);
      } else {
        root.style.removeProperty("--lf-baseline-offset");
        document.body.classList.remove("lf-debug-grid");
      }
      event.preventDefault();
    }
  });
});
