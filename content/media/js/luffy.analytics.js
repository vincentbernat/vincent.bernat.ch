/* Simple analytics. Half-stolen from Bear Blog. */

luffy.do(() => {
    document.addEventListener("load", () => {
        if (navigator.webdriver) return;
        const sendHit = () => {
            new Image().src = `/hit${window.location.pathname}`;
        };
        document.addEventListener("touchmove", sendHit, {
            once: true,
        });
        document.addEventListener("mousemove", sendHit, {
            once: true,
        });
    });
});
