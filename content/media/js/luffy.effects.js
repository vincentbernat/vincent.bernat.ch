/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    var e;
    /* -- Effect 1:
          Resize #lf-page-{1,2} to match size of main page
       -- */
    e = function() {
	/* Set appropriate height for rotated pages */
	$(".mod-csstransforms #lf-page-1, .mod-csstransforms #lf-page-2")
	    .css("height",$("#lf-page").innerHeight())
	    .css("width", $("#lf-page").innerWidth())
	    .show();
    }();

    /* -- Effect 3:
          Scrolly headers (stolen from Steve Losh)
	  https://github.com/sjl/stevelosh/blob/master/media/js/sjl.js
       -- */
    e = function() {
	if (!Modernizr.csstransforms || !Modernizr.rgba || !Modernizr.textshadow)
	    return;
	var header = $("<div>").addClass("lf-scrolling-header");
	var base = $("article div[role='main']")
	$("#lf-page").prepend(header);
	$(window).scroll(function() {
	    // Locate the appropriate title to display
	    var h1s = base.find("h1");
	    var y = $(window).scrollTop();
	    var title = h1s.filter(function() {
		return ($(this).offset().top < y);
	    }).last().text();
	    if (!(title != null) || y > base.offset().top + base.height()) {
		header.hide();
	    } else {
		header.html(title);
		// Compute opacity before displaying
		var distances = h1s.map(function() {
		    var d1, d2;
		    d1 = $(this).offset().top - y;
		    d2 = $(this).offset().top - y - header.width();
		    if (d1*d2 < 0) {
			// Our scrolling header is between two sections
			return 0;
		    } else {
			if (d1 < 0) d1 = -d1;
			if (d2 < 0) d2 = -d2;
			return Math.min(d1,d2);
		    }
		});
		var opacity = Math.min.apply(Math, distances)/100;
		if (opacity > 1) opacity = 1;
		header.css({
		    top: y - $("#lf-page").offset().top,
		    opacity: opacity
		}).show();
	    }
	});
    }();

    /* -- Effect 4:
          Add captions to images
       -- */
    e = function() {
	/* IE 7 is not able to render properly, just don't modify
	 * anything for it */
	if ($.browser.msie && parseInt($.browser.version, 10) < 8)
	    return;
	$("article img[title]").each(function() {
	    var img = $(this), title = img.attr("title");
	    if (img.parent().is("a")) img = img.parent();
	    $("<div>")
		.addClass("lf-caption")
		.text(title)
		.appendTo(img.parent());
	    img.parent().addClass("lf-captioned");
	    img.hover(function() {
		img.next().hide();
	    }, function() {
		img.next().show();
	    });
	});
    }();

    /* -- Effect 5:
          Highlight appropriate tag block
       -- */
    e = function() {
	if (location.hash.match("^#tag-")) {
	    $(".lf-list-tags .lf-tag").filter(function() {
		return $(this).prop("id") == location.hash.substr(1);
	    }).addClass("lf-tag-selected");
	}
    }();

};
