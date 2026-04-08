/* Keyboard shortcuts */

luffy.do(() => {
  const searchForm = document.querySelector("#lf-search-query") || document.querySelector("#lf-search-input");
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && !event.altKey && !event.shiftKey && !event.metaKey && event.key === "k") {
      if (document.activeElement !== searchForm) {
        event.preventDefault();
        searchForm.focus();
      }
    }
    if (event.ctrlKey && event.altKey && !event.shiftKey && !event.metaKey && event.key === "g") {
      document.body.classList.toggle("lf-debug-grid");
      event.preventDefault();
    }
  });
});
