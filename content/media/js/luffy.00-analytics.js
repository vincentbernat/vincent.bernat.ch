/* Simple analytics, reported to GoatCounter. Use of touchmove/mousemove to
   filter bots was stolen from Bear Blog. */

luffy.do(() => {
  const canonical = document.querySelector('link[rel="canonical"]')?.href;
  if (
    !canonical ||
    navigator.webdriver ||
    (localStorage && localStorage.getItem("skipgc"))
  )
    return;
  const url = new URL(canonical);

  /* Send a hit to GoatCounter through the /hit endpoint. It may not exist, use `luffy.count?.()`. */
  luffy.count = (vars = {}) => {
    const params = new URLSearchParams({
      p: vars.event ?? vars.path ?? url.pathname,
      t: vars.title ?? document.title,
      r: vars.referrer ?? (vars.event ? canonical : document.referrer),
      q: vars.query ?? location.search,
      s:
        vars.screen ??
        ((w) => {
          // Round down to 10px (when < 1000), 20px (when < 2000),
          // 40px (when < 3000).
          const step = 10 * 2 ** Math.min(2, Math.floor(w / 1000));
          return `${Math.floor(w / step) * step}`;
        })(document.documentElement.clientWidth),
      e: !!vars.event,
      rnd: Math.random().toString(36).slice(2, 7),
    });
    fetch(`/hit?${params}`, { keepalive: true }).catch(() => {});
  };

  let sent = false;
  const sendHit = () => {
    if (sent) return;
    sent = true;
    luffy.count();
  };

  /* Assume we are human if we trigger one of these interactions. pointerdown
       happen a bit before click and gives more time to send a beacon. */
  ["touchmove", "mousemove", "keydown", "pointerdown"].forEach((eventName) =>
    document.addEventListener(eventName, sendHit, {
      once: true,
      passive: true,
    }),
  );
});
