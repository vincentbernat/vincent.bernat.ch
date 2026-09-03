/* Comment system (using Isso) */
luffy.do(() => {
  // Don't do anything if there is no comment
  const el = document.getElementById("isso-thread");
  const links = document.querySelector(
    '#lf-bottomlinks a[href="#isso-thread"]',
  );
  if (!el || !links) return;

  // Function to load Isso once
  let done = false;
  const load = () => {
    if (done) return;
    done = true;

    links.closest("li")?.remove();
    luffy.load("isso.css");
    luffy.load("isso.js");
  };

  // Load if we have an anchor
  const onHashChange = () => {
    if (/^#isso-(\d+|thread)$/.test(location.hash)) {
      load();
    }
  };
  window.addEventListener("hashchange", onHashChange);
  onHashChange();

  // Load when it becomes visible
  const footer = document.querySelector("footer");
  if (window.IntersectionObserver && footer) {
    const observer = new window.IntersectionObserver((entries, observer) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        load();
      }
    });
    observer.observe(footer);
  }
});
