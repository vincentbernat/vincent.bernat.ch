/* Keyboard shortcuts and back to top */

luffy.do(() => {
  document.querySelector(".lf-backtotop a")?.addEventListener("click", (event) => {
    window.scrollTo(0);
    event.preventDefault();
  });

  const searchForm = document.querySelector("#lf-search-query") || document.querySelector("#lf-search-input");
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && !event.altKey && !event.shiftKey && !event.metaKey && event.key === "k") {
      if (document.activeElement !== searchForm) {
        searchForm.focus();
        event.preventDefault();
      }
    }
    if (event.ctrlKey && event.altKey && !event.shiftKey && !event.metaKey && event.key === "g") {
      document.body.classList.toggle("lf-debug-grid");
      event.preventDefault();
    }
  });
});
