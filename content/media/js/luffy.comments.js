/* Comment system (using Disqus) */

luffy.s.push(function() {
    // Don't do anything if there is no comment
    var el = document.getElementById("disqus_thread");
    if (el === null || el === undefined || el.addEventListener === undefined) return;
    var links = document.querySelectorAll('#lf-bottomlinks a[href=""]'), i;

    // Load Disqus on click
    var load = function() {
	var done = false;
	return function(e) {
            if (e) e.preventDefault();
	    if (done) return;
	    done = true;	// Don't want to load twice.

            // Set some variables for Disqus
            var l = window.location, lang = document.documentElement.lang;
            var pathname = l.pathname.replace(/\.html$/, "");
            window.disqus_shortname = el.dataset.disqusShortname;
            window.disqus_identifier = pathname + ".html";
            window.disqus_url = l.protocol + "//" + l.hostname + (l.port ? ':' + l.port: '') + pathname;
            window.disqus_title = document.title.split(" | ")[0];
            window.disqus_config = function () {
                this.language = lang;
            };

            // Create a script tag
            var s = document.createElement("script");
            s.type = "text/javascript";
            s.async = true;
            s.src = 'https://' + window.disqus_shortname + '.disqus.com/embed.js';
            (document.getElementsByTagName("head")[0] ||
             document.getElementsByTagName("body")[0])
                .appendChild(s);

            // Hide links
            for (i = 0; i < links.length; i++) {
                var parent = links[i].parentNode;
                while (parent && parent.tagName !== "LI")
                    parent = parent.parentNode;
                if (parent) {
                    parent.parentNode.removeChild(parent);
                }
            }
            return;
	}
    }();

    for (i = 0; i < links.length; i++) {
        links[i].addEventListener('click', load, false);
    }

    /* Load if we have an anchor */
    var onHashChange = function() {
        if (location.hash.match("^#comment-[0-9]+")) {
            load();
        }
    };
    if (window.addEventListener) {
        window.addEventListener("hashchange", onHashChange);
    }
    onHashChange();
});
