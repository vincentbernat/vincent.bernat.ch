---
combine:
    files:
      - luffy.*.js
    where: bottom
    remove: yes
---

var luffy = luffy || {s: []};
(function() {
  var e = function(fn) {
    try {
      fn();
    } catch (e) {
      (console.error || console.log).call(console, e);
    }
  };
  for (var i = 0; i < luffy.s.length; i++) {
    e(luffy.s[i])
  }
  luffy.s = { push: e };        // "Like" an array.

  // Tell we can do JS
  var html = document.getElementsByTagName("html")[0];
  html.className = html.className.replace(/\bnojs\b/, 'js');

})();
