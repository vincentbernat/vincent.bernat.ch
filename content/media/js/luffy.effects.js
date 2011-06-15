/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    var resizeTimer = null;

    /* Set appropriate height for rotated pages */
    var updatePageSizes = function() {
	$(".csstransforms #lf-page-1, .csstransforms #lf-page-2")
	    .css("height",$("#lf-page").innerHeight())
	    .css("width", $("#lf-page").innerWidth())
	    .show();
	resizeTimer = null;
    }
    
    /* Fire on start */
    updatePageSizes();

    /* Fire on resize (but not too often) */
    $(window).resize(function() {
	if (resizeTimer) clearTimeout(resizeTimer);
	resizeTimer = setTimeout(updatePageSizes, 100);
    });

    /* What's window size anyway? */
    if (typeof(_gaq) !== 'undefined') {
	var win = $(window);
	_gaq.push(['_trackEvent', 'Viewport',
		   win.width() + 'x' + win.height(),
		   win.width()]);
    }
};
