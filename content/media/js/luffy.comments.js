/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    $("#lf-disqus").click(function() {
	var loading = $(this).text('Loading/Chargement...');
        var src = 'http://' + disqus_shortname + '.disqus.com/embed.js';
	if (typeof(_gaq) !== 'undefined') {
	    _gaq.push(['_trackEvent', 'Comments',
		       document.title.split(" | ")[0]]);
	}
	yepnope({ load: src,
		  complete: function() {
		      loading.hide();
		  }});
    });

    /* Display comments now if there is a comment anchor in our URL */
    if (location.hash.match("^#comment-")) {
	var comment = location.hash.substr(9);
	var style = "#dsq-comment-" + comment + " .dsq-comment-header { " +
	    "background-color: #FBE686; background-image: none !important; border:3px solid #FBC586; }";
	/* Highlight the target comment */
	$("head").append("<style>" + style + "</style>");
	/* Scroll to comments before Disqus is loading */
	if (typeof window.scroll == 'function') {
	    window.scroll(0, $("#lf-disqus").offset().top);
	}
	/* Make Disqus load */
	$("#lf-disqus").click();
    }
};
