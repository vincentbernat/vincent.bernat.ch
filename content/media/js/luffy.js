---
combine:
    files:
      - luffy.*.js
    where: bottom
    remove: yes
---

var luffy = luffy || {s: [],
                      load: function(what, onload) {
                        // Lazy loading of some resources.
                        //  <script data-src="..." data-name="gallery.js"></script>
                        //  <link rel="stylesheet" data-href="..." href="data:text/css;base64," data-name="gallery.css">
                        var el = document.querySelector('script[data-name="' + what + '"]') ||
                            document.querySelector('link[data-name="' + what + '"]');
                        if (!el) throw("cannot load " + what);
                        if (onload) el.onload = onload;
                        for (var attr in el.dataset) {
                          if (attr != "name") el[attr] = el.dataset[attr];
                        }
                      }
                     };
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
  var cl = document.getElementsByTagName("html")[0].classList;
  cl.remove('nojs');
  cl.add('js');

})();
