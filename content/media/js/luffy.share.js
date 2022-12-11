/* Handle Web Share API */

luffy.do(() => {
  const el = document.querySelector(".lf-webshare > a");
  if (!el) return;
  if (!navigator.share) {
    el.parentNode.style.display = "none";
    return;
  }

  el.addEventListener("click", (event) => {
    event.preventDefault();
    navigator.share({
      text: document.title, // title is usually ignored
      url: document.querySelector("link[rel=canonical]").href,
    });
  });
});
