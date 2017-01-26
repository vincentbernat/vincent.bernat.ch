/* Mangle the URL to get the canonical one. */

var luffy = luffy || {};
luffy.url = function() {
  if (window.history && window.history.replaceState) {
    // Look for canonical tag.
    var link = document.querySelector("link[rel='canonical']");
    if (link && link.getAttribute("href") !== window.location.href) {
      window.history.replaceState('', '', link.getAttribute("href"));
    }
  }
};
