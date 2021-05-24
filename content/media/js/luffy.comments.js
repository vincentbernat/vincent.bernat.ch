/* Comment system (using Isso) */

luffy.do(function() {
    // Don't do anything if there is no comment
    var el = document.getElementById("isso-thread"),
        links = document.querySelectorAll('#lf-bottomlinks a[href="#isso-thread"]'),
        i;
    if (!el) return;

    // Function to load Isso
    var load = function() {
        var done = false;
        return function() {
            if (done) return;
            done = true;        // Don't want to load twice.

            luffy.load("isso.js", function() {
                // Hide links
                for (i = 0; i < links.length; i++) {
                    var parent = links[i].parentNode;
                    while (parent && parent.tagName !== "LI")
                        parent = parent.parentNode;
                    if (parent) {
                        parent.style.visibility = 'hidden';
                    }
                }
            });
        }
    }();

    // Load if we have an anchor
    var onHashChange = function() {
        if (location.hash.match("^#isso-([0-9]+|thread)$")) {
            load();
        }
    };
    window.addEventListener("hashchange", onHashChange);
    onHashChange();

    // Load when it becomes visible
    if ('IntersectionObserver' in window && links) {
        var observer = new window.IntersectionObserver(function(entries, observer) {
            for (i = 0; i < entries.length; i++) {
                if (!entries[i].isIntersecting)
                    continue;
                observer.unobserve(links[0]);
                load();
            }
        });
        observer.observe(document.querySelectorAll('footer')[0]);
    }
});
