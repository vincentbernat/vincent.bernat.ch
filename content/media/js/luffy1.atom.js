/* Inside the Atom feed, load the HTML rendering. In the HTML version, display
   the Atom feed URL. */
if (document instanceof XMLDocument) {
  location.replace(document.querySelector("noscript a").href);
} else {
  const feed = document.querySelector('link[type="application/atom+xml"]');
  if (feed) history.replaceState(null, "", feed.href);
}
