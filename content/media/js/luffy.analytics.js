/* Simple analytics. Half-stolen from Bear Blog. */

luffy.do(() => {
    const canonical = document.querySelector('link[rel="canonical"]')?.href;
    if (navigator.webdriver || !canonical) return;
    const url = new URL(canonical);
    const sendHit = () => {
        new Image().src = `/hit/${url.hostname}${url.pathname}`;
    };
    document.addEventListener("touchmove", sendHit, {
        once: true,
    });
    document.addEventListener("mousemove", sendHit, {
        once: true,
    });
});
