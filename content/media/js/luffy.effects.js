/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    var e;
    /* -- Effect 1:
          Resize #lf-page-{1,2} to match size of main page
       -- */
    e = function() {
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
    }();

    /* -- Effect 2:
          Log the window size to Google Analytics (not really an effect)
       -- */
    e = function() {
	if (typeof(_gaq) !== 'undefined') {
	    var win = $(window);
	    _gaq.push(['_trackEvent', 'Viewport',
		       'Size',
		       win.width() + 'x' + win.height(),
		       win.width()]);
	}
    }();
};
