---
combine:
    files: luffy.*.js
    where: top
    remove: yes
---

$(function() {
    luffy.mathjax();
    luffy.effects();
    luffy.search();
    luffy.timeago();
    luffy.comments();
    luffy.gallery();
});
