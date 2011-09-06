/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    /* Load Disqus when clicking on the comment bar */
    $("#lf-disqus").show().click(function() {
	var loading = $(this).text('Loading/Chargement...');
        var src = '//' + disqus_shortname + '.disqus.com/embed.js';
	yepnope({ load: src,
		  complete: function() {
		      loading.hide();
		  }});
    });

    /* Display comments when the current location point to a comment */
    var display_comment = function(comment) {
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
    /* Display comments now if there is a comment anchor in our URL */
    if (location.hash.match("^#comment-[0-9]+")) {
	var comment = location.hash.substr(9);
	display_comment(comment);
    }
    /* Also display them when we click on a link to a comment to the
       same page */
    $("article a").filter(function (index) {
	return (this.host == location.host) &&
	    (this.pathname == location.pathname ||
	     "/" + this.pathname == location.pathname) &&
	    (typeof this.hash !== 'undefined') &&
	    (this.hash.match("^#comment-[0-9]+"));
    }).click(function() {
	var comment = this.hash.substr(9);
	display_comment(comment);
    });
};
