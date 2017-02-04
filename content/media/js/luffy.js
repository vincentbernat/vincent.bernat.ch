---
combine:
    files:
      - script.js
      - luffy.*.js
    where: top
    remove: yes
---

var scripts = [luffy.mathjax,
               luffy.url,
               luffy.captions,
               luffy.footnotes,
               luffy.comments,
               luffy.gallery];
for (var i = 0; i < scripts.length; i++) {
  try {
    scripts[i]();
  } catch (e) {
    (console.error || console.log).call(console, e);
  }
}
