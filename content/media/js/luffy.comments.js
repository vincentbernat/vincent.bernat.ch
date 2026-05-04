/* Comment system (using Isso) */

luffy.do(() => {
  // Don't do anything if there is no comment
  const el = document.getElementById("isso-thread");
  const links = document.querySelector(
    '#lf-bottomlinks a[href="#isso-thread"]',
  );
  if (!el) return;

  // Function to load Isso
  const load = (() => {
    let done = false;
    return () => {
      if (done || !links) return;
      done = true; // Don't want to load twice.

      let parent = links.parentNode;
      while (parent && parent.tagName !== "LI") parent = parent.parentNode;
      if (parent) {
        parent.remove();
      }

      luffy.load("isso.css");
      luffy.load("isso.js");
    };
  })();

  // Load if we have an anchor
  const onHashChange = () => {
    if (location.hash.match("^#isso-([0-9]+|thread)$")) {
      load();
    }
  };
  window.addEventListener("hashchange", onHashChange);
  onHashChange();

  // Load when it becomes visible
  if ("IntersectionObserver" in window && links) {
    const footer = document.querySelector("footer");
    const observer = new window.IntersectionObserver((entries, observer) => {
      for (let i = 0; i < entries.length; i++) {
        if (!entries[i].isIntersecting) continue;
        observer.unobserve(footer);
        load();
      }
    });
    observer.observe(footer);
  }
});
