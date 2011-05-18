/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    /* Set appropriate height for rotated pages */
    $(".csstransforms #lf-page-1, .csstransforms #lf-page-2")
	.css("height",$("#lf-page").innerHeight()).show();
    /* Animate the language box */
    $("#lf-links").css('left',
		       '-' + $("#lf-links").css('width'))
	.animate({left: 0}, 'slow');
};
