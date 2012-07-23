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
