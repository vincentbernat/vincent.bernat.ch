/* Simple analytics, reported to GoatCounter through the /hit endpoint. */

luffy.do(() => {
    const canonical = document.querySelector('link[rel="canonical"]')?.href;
    if (
        navigator.webdriver ||
        !canonical ||
        (localStorage && localStorage.getItem("skipgc"))
    )
        return;
    let sent = false;
    const url = new URL(canonical);
    const sendHit = () => {
        if (sent) return;
        sent = true;
        const params = new URLSearchParams({
            p: url.pathname,
            t: document.title,
            r: document.referrer,
            q: location.search,
            s: `${screen.width}`,
            rnd: Math.random().toString(36).substr(2, 5),
        });
        fetch(`/hit?${params}`).catch(() => {});
    };
    document.addEventListener("touchmove", sendHit, {
        once: true,
    });
    document.addEventListener("mousemove", sendHit, {
        once: true,
    });
});
