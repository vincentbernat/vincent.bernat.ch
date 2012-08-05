/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    var e;
    /* -- Effect 1:
          Resize #lf-page-{1,2} to match size of main page
       -- */
    e = function() {
	/* Set appropriate height for rotated pages */
	$(".csstransforms #lf-page-1, .csstransforms #lf-page-2")
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
	$("#lf-page").prepend(header);
	$(window).scroll(function() {
	    // Locate the appropriate title to display
	    var h1s = $("article div[role='main'] h1");
	    var y = $(window).scrollTop();
	    var title = h1s.filter(function() {
		return $(this).offset().top < y;
	    }).last().html();
	    if (!(title != null)) {
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
		}).toggle(opacity > 0);
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

    /* -- Effect 6:
          Replace missing ligatures (œ)
       -- */
    /* This code was mostly stolen here:
       http://johannburkard.de/resources/Johann/jquery.highlight-3.js
       MIT licensed by Johann Burkard
    */
    e = function() {
	var ligatures = { "œ": "oe", "Œ": "OE"};
	/* On each leaf node, we will achieve substitution */
	function innerSubstitution(node) {
	    var skip = 0;
	    if (node.nodeType == 3) {
		// This is a text node
		for (var ligature in ligatures) {
		var pos = node.data.indexOf(ligature);
		    if (pos >= 0) {
			var spannode = document.createElement('span');
			spannode.className = 'lf-ligature';
			var middlebit = node.splitText(pos);
			var endbit = middlebit.splitText(1);
			spannode.innerHTML = ligatures[ligature].charAt(1);
			node.data = node.data + ligatures[ligature].charAt(0);
			middlebit.parentNode.replaceChild(spannode, middlebit);
			skip = 1; break; // We should reanalyse again this node!
		    }
		}
	    } else if (node.nodeType == 1
		       && node.childNodes
		       && !/(script|style)/i.test(node.tagName)) {
		// Recurse inside this node
		for (var i = 0; i < node.childNodes.length; ++i) {
		    i += innerSubstitution(node.childNodes[i]);
		}
	    }
	    return skip;
	}
	$("article").each(function() {
	    innerSubstitution(this);
	});
    }();
};
