/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    $("#lf-disqus").click(function() {
	$(this).hide();
        var src = 'http://' + disqus_shortname + '.disqus.com/embed.js';
	yepnope(src);
    });
};
