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
    luffy.timeago();
    luffy.comments();
    luffy.gallery();
});
