/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    var el = document.getElementById("lf-disqus");	// Don't do anything if there is no comment
    if (el === null || el === undefined) return;

    /* Function to load Disqus */
    var load = function() {
	var done = false;
	return function() {
	    if (done) return;
	    done = true;	// Don't want to load twice.
	    el.innerHTML = 'Loading/Chargement...';
            var src = 'https://' + disqus_shortname + '.disqus.com/embed.js';
	    $script(src, function() {
		el.style.display = 'none';
	    });
	}
    }();

    el.style.display = 'block';
    el.addEventListener('click', load, false);

    /* Load if we have an anchor */
    if (location.hash.match("^#comment-[0-9]+")) {
        load();
    }

};
