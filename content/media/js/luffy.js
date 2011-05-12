---
combine:
    files: luffy.*.js
    where: top
    remove: yes
---

$(function() {
    luffy.effects();
    luffy.search();
    luffy.timeago();
    luffy.comments();
});
