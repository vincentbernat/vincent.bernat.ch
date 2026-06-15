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
            s: vars.screen ?? `${screen.width}`,
            e: !!vars.event,
            rnd: Math.random().toString(36).substr(2, 5),
        });
        fetch(`/hit?${params}`).catch(() => {});
    };

    let sent = false;
    const sendHit = () => {
        if (sent) return;
        sent = true;
        luffy.count();
    };
    document.addEventListener("touchmove", sendHit, {
        once: true,
    });
    document.addEventListener("mousemove", sendHit, {
        once: true,
    });
});
