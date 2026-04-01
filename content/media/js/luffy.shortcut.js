/* Keyboard shortcuts */

luffy.do(() => {
  const el = document.querySelector("#lf-search-query");
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && !event.altKey && !event.shiftKey && !event.metaKey && event.key === "k") {
      event.preventDefault();
      el.focus();
    }
    if (event.ctrlKey && event.altKey && !event.shiftKey && !event.metaKey && event.key === "g") {
      document.body.classList.toggle("lf-debug-grid");
      event.preventDefault();
    }
  });
});
