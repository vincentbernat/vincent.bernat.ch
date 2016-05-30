/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    var e;

    /* -- Effect 4:
          Add captions to images
       -- */
    e = function() {
        if (typeof document.querySelectorAll !== "function") return;
        var els = document.querySelectorAll("article img[title]"), i;
        for (i = 0; i < els.length; i++) {
            var el = els[i], title = el.getAttribute("title");
            if (el.parentNode.tagName.toLowerCase() === "a") {
                el = el.parentNode;
            }
            (function() {
                var caption = document.createElement("div");
                caption.className = "lf-caption";
                caption.innerText = caption.textContent = title;
                el.parentNode.appendChild(caption);
                el.parentNode.className += " lf-captioned";
                if (el.addEventListener) {
                    el.addEventListener("mouseover", function() {
                        caption.style.display = 'none';
                    });
                    el.addEventListener("mouseout", function() {
                        caption.style.display = 'block';
                    });
                }
            })();
	}
    }();

};
