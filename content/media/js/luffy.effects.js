/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    /* Set appropriate height for rotated pages */
    $(".csstransforms #lf-page-1, .csstransforms #lf-page-2")
	.css("height",$("#lf-page").innerHeight())
	.css("width", $("#lf-page").innerWidth())
	.show();
};
