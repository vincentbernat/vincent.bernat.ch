/* Simple analytics, reported to GoatCounter. Use of touchmove/mousemove to
   filter bots was stolen from Bear Blog. */

luffy.do(() => {
  const canonical = document.querySelector("link[rel=canonical]")?.href;
  if (
    !canonical ||
    navigator.webdriver ||
    (localStorage && localStorage.getItem("skipgc"))
  )
    return;
  const path = new URL(canonical).pathname;

  /* Send a hit to GoatCounter through the /hit endpoint. Call with `luffy.count?.()`. */
  luffy.count = ({ event, title } = {}) => {
    // Round down client width to 10px (when < 1000), 20px (when < 2000), 40px
    // (otherwise).
    const w = document.documentElement.clientWidth;
    const step = 10 << Math.min(2, (w / 1000) | 0);

    const params = new URLSearchParams({
      p: event || path,
      t: title || document.title,
      r: event ? canonical : document.referrer,
      q: location.search,
      s: w - (w % step),
      e: !!event,
      rnd: Math.random().toString(36).slice(2, 7),
    });
    fetch(`/hit?${params}`, { keepalive: true }).catch(() => {});
  };

  /* Assume we are human if we trigger one of these interactions. pointerdown
       happen a bit before click and gives more time to send a beacon. */
  const sendHit = luffy.once(() => luffy.count());
  ["touchmove", "mousemove", "keydown", "pointerdown"].forEach((eventName) =>
    document.addEventListener(eventName, sendHit, {
      once: true,
      passive: true,
    }),
  );
});
