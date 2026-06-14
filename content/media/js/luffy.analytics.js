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
        const hit = {
            path: url.pathname,
            title: document.title,
            ref: document.referrer,
            query: location.search,
            user_agent: navigator.userAgent,
            size: `${screen.width}`,
        };
        // Drop the enclosing braces: nginx wraps the rest back into the
        // GoatCounter API body and injects the visitor IP.
        fetch("/hit", {
            method: "POST",
            body: JSON.stringify(hit).slice(1, -1),
        }).catch(() => {});
    };
    document.addEventListener("touchmove", sendHit, {
        once: true,
    });
    document.addEventListener("mousemove", sendHit, {
        once: true,
    });
});
