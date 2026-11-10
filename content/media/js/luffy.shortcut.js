/* Keyboard shortcuts and back to top */

luffy.do(() => {
  // Back to top
  document
    .querySelector(".lf-backtotop a")
    ?.addEventListener("click", (event) => {
      luffy.count?.({
        event: "back-to-top",
        title: "Click on back to top link",
      });
      window.scrollTo(0, 0);
      event.preventDefault();
    });

  // For search
  const searchForm = document.querySelector(
    "#lf-search-query, #lf-search-input",
  );
  document.addEventListener("keydown", (event) => {
    if (
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      event.key === "k"
    ) {
      // Focus the search form.
      if (document.activeElement !== searchForm) {
        searchForm.focus();
        event.preventDefault();
      }
    }
  });

  // Debug chords: ←, ←, then a letter. The letter goes to a hidden input, so
  // the browser or another listener does not use it.
  let debugLoaded = null;
  const debug = () =>
    (debugLoaded ||= new Promise((resolve) => {
      luffy.load("luffy1.debug.css");
      luffy.load("luffy1.debug.js", resolve);
    }));
  const leftHasEffect = (event) => {
    if (event.defaultPrevented) return true;
    for (let el = event.target; el instanceof Element; el = el.parentElement) {
      if (el.isContentEditable || el.scrollLeft > 0) return true;
      if (el.matches("input, textarea, select, video, audio")) return true;
    }
    return false;
  };
  let lastLeft = 0; // time of the last ←, 0 after another key
  let input = null; // hidden input catching the letter
  let previous = null; // element with focus before the input
  let timer = null; // timeout to give up waiting for the letter
  const end = () => {
    // Stop waiting for debug action
    clearTimeout(timer);
    if (document.activeElement === input) {
      input.blur();
      previous?.focus({ preventScroll: true });
    }
  };
  const start = () => {
    // Start waiting for debug action
    if (!input) {
      input = document.createElement("input");
      input.tabIndex = -1;
      input.style.cssText =
        "position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none;font-size:16px";
      document.body.appendChild(input);
    }
    previous = document.activeElement;
    input.focus({ preventScroll: true });
    timer = setTimeout(end, 2000);
  };
  document.addEventListener("keydown", (event) => {
    if (input && event.target === input) {
      // Trigger the debug action
      event.preventDefault();
      end();
      debug().then(() => luffy.debug?.[event.key]?.());
      return;
    }
    if (
      event.key !== "ArrowLeft" ||
      event.ctrlKey ||
      event.altKey ||
      event.shiftKey ||
      event.metaKey ||
      leftHasEffect(event)
    ) {
      // Reset state
      lastLeft = 0;
      return;
    }
    // ←
    event.preventDefault();
    const now = Date.now();
    if (now - lastLeft < 1000) {
      lastLeft = 0;
      start();
    } else lastLeft = now;
  });
});
