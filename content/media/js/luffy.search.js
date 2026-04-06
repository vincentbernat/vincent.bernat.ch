// Override navbar search to use local Pagefind search
luffy.do(() => {
  return; // disabled until I make everything work correctly!
  const form = document.getElementById("lf-search");
  if (!form) return;
  const lang = document.documentElement.lang;
  const devMode = location.pathname.endsWith(".html");
  form.action = `/${lang}/search${devMode ? ".html" : ""}`;
  form.querySelectorAll("input[type=hidden]").forEach((el) => el.remove());
});
