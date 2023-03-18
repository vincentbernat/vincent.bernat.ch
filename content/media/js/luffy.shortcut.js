/* Keyboard shortcuts */

luffy.do(() => {
  const el = document.querySelector("#lf-search-query");
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key === "k") {
      el.focus();
      return true;
    }
  });
});
