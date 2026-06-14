/* Simple analytics, reported to GoatCounter through the /hit endpoint. */

luffy.do(() => {
    const canonical = document.querySelector('link[rel="canonical"]')?.href;
    if (navigator.webdriver || !canonical) return;
    const url = new URL(canonical);
    let sent = false;
    const sendHit = () => {
        if (sent) return;
        sent = true;
        const data = {
            hits: [
                {
                    path: url.pathname,
                    title: document.title,
                    ref: document.referrer,
                    query: location.search,
                    size: `${screen.width}`,
                    user_agent: navigator.userAgent,
                },
            ],
        };
        fetch("/hit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        }).catch(() => {});
    };
    document.addEventListener("touchmove", sendHit, {
        once: true,
    });
    document.addEventListener("mousemove", sendHit, {
        once: true,
    });
});
