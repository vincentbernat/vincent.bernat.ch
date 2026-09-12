/* Replace the Atom feed with its web page when viewed in a browser. The link to
   this page is in the noscript element. */
(() => {
  const link = document.querySelector("noscript a");
  if (!link || !window.fetch || !window.DOMParser) return showFeed();
  const xhtml = "http://www.w3.org/1999/xhtml";
  fetch(link.href)
    .then((response) => response.text())
    .then((html) => {
      const page = new DOMParser().parseFromString(html, "text/html");
      document.replaceChild(
        document.adoptNode(page.documentElement),
        document.documentElement,
      );
      document.documentElement.classList.add("rss");

      // Scripts moved from another document do not run. Create new ones.
      for (const old of document.querySelectorAll("script")) {
        const script = document.createElementNS(xhtml, "script");
        for (const { name, value } of old.attributes)
          script.setAttribute(name, value);
        script.textContent = old.textContent;
        old.replaceWith(script);
      }
    });
})();
