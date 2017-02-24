/* Add captions to images. */

var luffy = luffy || {};
luffy.captions = function() {
    if (typeof document.querySelectorAll !== "function") return;
    var els = document.querySelectorAll("article img[title]"), i;
    for (i = 0; i < els.length; i++) {
        var el = els[i], title = el.getAttribute("title");
        if (el.parentNode.tagName.toLowerCase() === "a") {
            el = el.parentNode;
        }
        var caption = document.createElement("div");
        caption.className = "lf-caption";
        caption.innerText = caption.textContent = title;
        el.parentNode.appendChild(caption);
        el.parentNode.className += " lf-captioned";
    }
};
