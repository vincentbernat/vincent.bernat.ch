// Override navbar search to use local Pagefind search
(() => {
  try {
    if (!window.IntersectionObserver) return;
    const form = document.getElementById("lf-search");
    form?.setAttribute("action", form.dataset.action);
    form?.querySelectorAll("input[type=hidden]").forEach((el) => el.remove());
  } catch (e) {
    console.error(e);
  }
})();
