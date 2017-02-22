/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    // Don't do anything if there is no comment
    var el = document.getElementById("disqus_thread");
    if (el === null || el === undefined || el.addEventListener === undefined) return;

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

            var src = 'https://' + window.disqus_shortname + '.disqus.com/embed.js';
	    $script(src, function() {});
            return;
	}
    }();

    var links = el.querySelectorAll('a[href=""]'), i;
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

    // Display introduction text
    el.children[1].className = el.children[2].className;
    el.children[2].className = '';
};
