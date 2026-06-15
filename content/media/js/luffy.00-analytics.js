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
    const sendHit = async () => {
        if (sent) return;
        sent = true;
        /* Solve a simple proof-of-work before reporting the hit. */
        const encoder = new TextEncoder();
        const prefix = Math.random().toString(36).slice(2);
        const start = performance.now();
        for (let nonce = 0; ; nonce++) {
            const digest = new Uint8Array(
                await crypto.subtle.digest(
                    "SHA-256",
                    encoder.encode(prefix + nonce),
                ),
            );
            // 14-bit complexity.
            if (digest[0] === 0 && (digest[1] & 0xfc) === 0) break;
        }
        console.debug(`PoW solved in ${performance.now() - start}ms`);
        luffy.count();
    };
    ["touchmove", "mousemove", "keydown"].forEach((eventName) =>
        document.addEventListener(eventName, sendHit, {
            once: true,
            passive: true,
        }),
    );
});
