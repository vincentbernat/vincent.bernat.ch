---
combine:
    files:
      - script.js
      - luffy.*.js
    where: top
    remove: yes
---

$(function() {
    luffy.mathjax();
    luffy.effects();
    luffy.comments();
    luffy.gallery();
});
