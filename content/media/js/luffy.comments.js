/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    if ($("#disqus_thread").length > 0) {
	(function() {
            var src = 'http://' + disqus_shortname + '.disqus.com/embed.js';
	    yepnope(src);
	})();
    }
};
