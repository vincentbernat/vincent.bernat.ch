/* Handle image gallery */

luffy.do(() => {
    // Don't do anything if there is no gallery
    if (!document.querySelector(".lf-gallery")) return;

    // Otherwise, load CSS and script
    luffy.load("gallery.js", () => { baguetteBox.run('.lf-gallery'); });
    luffy.load("gallery.css");
});
