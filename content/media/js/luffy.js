---
combine:
    files:
      - luffy.*.js
    where: bottom
    remove: yes
---
window.luffy = {
  do(fn) {
    // Create a scope, catch errors to not propagate further, allow early return.
    try {
      fn();
    } catch (e) {
      console.error(e);
    }
  },
  once(fn) {
    // Return a function calling `fn` only the first time.
    let done = false;
    return (...args) => {
      if (done) return;
      done = true;
      return fn(...args);
    };
  },
  load(what, onload) {
    // Lazy loading of some resources. `data-src`, `data-href`, `data-integrity`
    // attributes are copied to `src`, `href`, `integrity` respectively.
    //
    //  <script data-src="..." data-name="gallery.js"></script>
    //  <link rel="stylesheet" data-href="..." href="data:text/css;base64," data-name="gallery.css">
    const el = document.querySelector(
      `script[data-name="${what}"], link[data-name="${what}"]`,
    );
    if (!el) return;
    if (onload) el.onload = onload;
    for (const k of ["integrity", "href", "src"])
      if (el.dataset[k]) el[k] = el.dataset[k];
  },
};
