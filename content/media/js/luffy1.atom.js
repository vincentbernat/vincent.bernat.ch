/* In the HTML rendering of the Atom feed, display the Atom feed URL. */
luffy.do(() => {
    const feed = document.querySelector('link[type="application/atom+xml"]');
    if (feed) history.replaceState(null, "", feed.href);
});
