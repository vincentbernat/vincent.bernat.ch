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
  load(what, onload) {
    // Lazy loading of some resources.
    //  <script data-src="..." data-name="gallery.js"></script>
    //  <link rel="stylesheet" data-href="..." href="data:text/css;base64," data-name="gallery.css">
    const el = document.querySelector(
      `script[data-name="${what}"], link[data-name="${what}"]`,
    );
    if (!el) throw `cannot load ${what}`;
    if (onload) el.onload = onload;
    for (const attr in el.dataset) {
      if (attr != "name") el[attr] = el.dataset[attr];
    }
  },
};
