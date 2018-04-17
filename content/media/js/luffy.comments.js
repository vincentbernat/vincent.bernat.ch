/* Comment system (using Isso) */

luffy.s.push(function() {
    // Don't do anything if there is no comment
    var el = document.getElementById("isso-thread");
    if (el === null || el === undefined || el.addEventListener === undefined) return;
    var links = document.querySelectorAll('#lf-bottomlinks a[href=""]'), i;

    // Load Isso on click
    var load = function() {
	var done = false;
	return function(e) {
            if (e) e.preventDefault();
	    if (done) return;
	    done = true;	// Don't want to load twice.

            var script = document.querySelector('script[data-name="isso.js"]');
            script.onload = function() {
                // Hide links
                for (i = 0; i < links.length; i++) {
                    var parent = links[i].parentNode;
                    while (parent && parent.tagName !== "LI")
                        parent = parent.parentNode;
                    if (parent) {
                        parent.parentNode.removeChild(parent);
                    }
                }
            };
            script.src = script.dataset.src;
	}
    }();

    for (i = 0; i < links.length; i++) {
        links[i].addEventListener('click', load, false);
    }

    // Load if we have an anchor
    var onHashChange = function() {
        if (location.hash.match("^#isso-[0-9]+")) {
            load();
        }
    };
    if (window.addEventListener) {
        window.addEventListener("hashchange", onHashChange);
    }
    onHashChange();

    // Load when it becomes visible
    if ('IntersectionObserver' in window) {
        var observer = new window.IntersectionObserver(function(entries, observer) {
            for (i = 0; i < entries.length; i++) {
                if (!entries[i].isIntersecting)
                    continue;
                observer.unobserve(links[0]);
                load();
            }
        });
        observer.observe(links[0]);
    }
});
