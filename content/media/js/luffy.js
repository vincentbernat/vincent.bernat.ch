---
combine:
    files:
      - luffy.*.js
    where: bottom
    remove: yes
---

var ___ = function(fn) {
  try {
    fn();
  } catch (e) {
    (console.error || console.log).call(console, e);
  }
};
