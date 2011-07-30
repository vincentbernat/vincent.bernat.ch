/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    var e;
    /* -- Effect 1:
          Resize #lf-page-{1,2} to match size of main page
       -- */
    e = function() {
	/* Set appropriate height for rotated pages */
	var updatePageSizes = function() {
	    $(".csstransforms #lf-page-1, .csstransforms #lf-page-2")
		.css("height",$("#lf-page").innerHeight())
		.css("width", $("#lf-page").innerWidth())
		.show();
	}();
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

    /* -- Effect 3:
          Scrolly headers (stolen from Steve Losh)
	  https://github.com/sjl/stevelosh/blob/master/media/js/sjl.js
       -- */
    e = function() {
	var header = $('<div id="lf-scrolling-header" />');
	var h1s = $(".lf-article #lf-main h1");
	var soff = 75;
	$('body').append(header[0]);
	$(window).scroll(function() {
	    var width = $("#lf-pages").first().offset()['left'] - 25;
	    if (width < 100) {
		header.hide();
		return;
	    }
	    var y = $(window).scrollTop(); // Current position
	    var title = null;		   // Title to display
	    h1s.each(function() {
		// Do we need to display this specific header?
		var header_y = $(this).offset()['top'] - soff;
		if (y < header_y) return false;
		// typogrify is adding a lot of non breakable spaces
		title = $(this).html().replace(/&nbsp;/g, ' ');
	    });
	    if (title === null) {
		header.hide();
	    } else {
		var size = "18px";
		if (width < 150) {
		    size = "12px";
		}
		header.css({ top: soff,
			     'font-size': size,
			     width: width }).html(title).show();
	    }
	});
    }();
};
