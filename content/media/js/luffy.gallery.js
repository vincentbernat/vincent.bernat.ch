/* Handle image gallery */

luffy.s.push(function() {
    // Don't do anything if there is no gallery
    if (!document.querySelector(".lf-gallery")) return;

    // Otherwise, load CSS and script
    var script = document.querySelector('script[data-name="gallery.js"]');
    script.onload = function() { baguetteBox.run('.lf-gallery'); };
    script.integrity = script.dataset.integrity || "";
    script.src = script.dataset.src;
    var css = document.querySelector('link[data-name="gallery.css"]');
    css.integrity = css.dataset.integrity || "";
    css.href = css.dataset.href;
});
