/* Mangle the URL to get the canonical one. */

var luffy = luffy || {};
luffy.url = function() {
  if (window.history && window.history.replaceState) {
    var link = document.querySelector("link[rel='canonical']");
    if (link) {
      var canonical = link.getAttribute('href');
      if (canonical) {
        canonical += window.location.hash;
        if (canonical !== window.location.href) {
          window.history.replaceState('', '', canonical);
        }
      }
    }
  }
};
