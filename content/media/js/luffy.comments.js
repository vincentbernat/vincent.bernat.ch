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
	    yepnope({ load: src,
		      complete: function() {
			  loading.hide();
		      }});
	}
    }();

    el
	.show()			// Show because JS is enabled
	.click(load);		// Load on click

    // If this is Googlebot, load comments right now (maybe comments will be indexed)
    if (/googlebot/i.test(navigator.userAgent)) load();

    /* Load on scroll to bottom */
    $(window).scroll(function() {
	var bottom = $(window).scrollTop() + $(window).height();
	var top = el.offset().top - 300;
	if (bottom >= top) load();
    });

    /* Display comments when the current location point to a comment */
    var display_comment = function(comment) {
	/* Highlight the target comment */
	var style = "#dsq-comment-" + comment + " .dsq-comment-header { " +
	    "background-color: #FBE686; background-image: none !important; " +
	    "border:3px solid #FBC586; }";
	$("head").append("<style>" + style + "</style>");

	/* Scroll to comment(s) */
	if ('object' == typeof window.scroll ||
	    'function' == typeof window.scroll) {
	    var el = $("#dsq-comment-" + comment);
	    window.scroll(0, (el.length?el:$("#disqus_thread")).offset().top);
	}

	load();			// Make Disqus load if needed
    }

    /* Display anchored comment */
    if (location.hash.match("^#comment-[0-9]+")) {
	var comment = location.hash.substr(9);
	display_comment(comment);
    }

    /* Also display them when we click on a link to a comment to the
       same page */
    $("article a").filter(function (index) {
	return (this.hostname == location.hostname) &&
	    (this.pathname == location.pathname ||
	     "/" + this.pathname == location.pathname) &&
	    (typeof this.hash !== 'undefined') &&
	    (this.hash.match("^#comment-[0-9]+"));
    }).click(function() {
	var comment = this.hash.substr(9);
	display_comment(comment);
    });
};
