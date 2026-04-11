// Override navbar search to use local Pagefind search
luffy.do(() => {
  const form = document.getElementById("lf-search");
  form?.setAttribute("action", form.dataset.action);
  form?.querySelectorAll("input[type=hidden]").forEach((el) => el.remove());
});
