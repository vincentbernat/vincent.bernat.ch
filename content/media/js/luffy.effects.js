/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    if (typeof document.querySelectorAll !== "function") return;
    var e;

    /* -- Effect 1:
          Add captions to images
       -- */
    e = function() {
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

    /* -- Effect 2:
          Turn footnotes to sidenotes
          -- */
    e = function() {
        var footnotes = document.querySelector("#lf-main .footnote ol"),
            footnoteReferences = document.querySelectorAll("#lf-main sup[id^=fnref-]"),
            i;
        for (i = 0; i < footnoteReferences.length; i++) {
            var footnoteReference = footnoteReferences[i],
                footnoteName = footnoteReference.id.replace(/^fnref-/, ''),
                footnote = footnotes.querySelector("li[id=fn-" + footnoteName + "]");
            /* Search for suitable parent and attach the side-note to it */
            var sidenote = document.createElement("aside"),
                parent = footnoteReference.parentNode;
            while (parent && parent.tagName !== "P" && parent.tagName !== "UL") parent = parent.parentNode;
            if (!parent || !footnote) {
                throw new Error("footnote `" + footnoteName + "' not found");
            }
            sidenote.className = "lf-sidenote";
            sidenote.innerHTML =
                "<sup class=\"lf-refmark\">" + footnoteReference.innerText + "</sup>"
                + footnote.innerHTML; // No ID, we don't want to shadow the original one
            parent.parentNode.insertBefore(sidenote, parent);
        }
        document.body.className += ' lf-has-sidenotes';
    }();

};
