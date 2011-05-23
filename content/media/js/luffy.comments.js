/* Comment system (using Disqus) */

var luffy = luffy || {};
luffy.comments = function() {
    $("#lf-disqus").click(function() {
	var loading = $(this).text('Loading/Chargement...');
        var src = 'http://' + disqus_shortname + '.disqus.com/embed.js';
	yepnope({ load: src,
		  complete: function() {
		      loading.hide();
		  }});
    });
};
