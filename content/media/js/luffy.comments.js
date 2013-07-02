/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    var el = $("#lf-disqus");	// Don't do anything if there is no comment
    if (!el.length) return;

    /* Function to load Disqus */
    var load = function() {
	var done = false;
	return function() {
	    if (done) return;
	    done = true;	// Don't want to load twice.
	    var loading = el.text('Loading/Chargement...');
            var src = '//' + disqus_shortname + '.disqus.com/embed.js';
	    $script(src, function() {
		loading.hide();
	    });
	}
    }();

    el
	.show()			// Show because JS is enabled
	.click(load);		// Load on click

    /* Load on scroll to bottom */
    $(window).scroll(function() {
	var bottom = $(window).scrollTop() + $(window).height();
	var top = el.offset().top - 300;
	if (bottom >= top) load();
    });

    /* Load if we have an anchor */
    if (location.hash.match("^#comment-[0-9]+")) {
        load();
    }

};
