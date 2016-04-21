---
combine:
    files:
      - script.js
      - luffy.*.js
    where: top
    remove: yes
---

var scripts = [luffy.mathjax,
               luffy.effects,
               luffy.comments,
               luffy.gallery];
for (var i = 0; i < scripts.length; i++) {
    scripts[i]();
}
