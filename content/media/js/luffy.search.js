// Override navbar search to use local Pagefind search
luffy.do(() => {
  const form = document.getElementById("lf-search");
  if (!window.IntersectionObserver || !form) return;
  form.setAttribute("action", form.dataset.action);
  form.querySelectorAll("input[type=hidden]").forEach((el) => el.remove());
});
