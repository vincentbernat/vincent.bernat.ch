/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    // Don't do anything if there is no comment
    var el = document.getElementById("disqus_thread");
    if (el === null || el === undefined) return;

    // Load Disqus on click
    var load = function() {
	var done = false;
	return function(e) {
            e.preventDefault();
	    if (done) return;
	    done = true;	// Don't want to load twice.
            var src = 'https://' + disqus_shortname + '.disqus.com/embed.js';
	    $script(src, function() {});
            return;
	}
    }();

    var links = el.querySelectorAll('a[href=""]'), i;
    for (i = 0; i < links.length; i++) {
        links[i].addEventListener('click', load, false);
    }

    /* Load if we have an anchor */
    if (location.hash.match("^#comment-[0-9]+")) {
        load();
    }

    // Display introduction text
    el.children[1].style.display = 'none';
    el.children[2].style.display = 'block';
};
