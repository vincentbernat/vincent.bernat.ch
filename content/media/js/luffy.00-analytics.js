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
            r: vars.referrer ?? document.referrer,
            q: vars.query ?? location.search,
            s:
                vars.screen ??
                `${Math.floor(document.documentElement.clientWidth / 10) * 10}`,
            e: !!vars.event,
            rnd: Math.random().toString(36).substr(2, 5),
        });
        fetch(`/hit?${params}`, { keepalive: true }).catch(() => {});
    };

    let sent = false;
    const sendHit = () => {
        if (sent) return;
        sent = true;
        luffy.count();

        /* Drop utm_* parameters from the displayed URL now that they were sent. */
        const clean = new URL(location.href);
        [...clean.searchParams.keys()]
            .filter((key) => key.startsWith("utm_"))
            .forEach((key) => clean.searchParams.delete(key));
        if (clean.href !== location.href)
            history.replaceState(history.state, "", clean.href);
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
