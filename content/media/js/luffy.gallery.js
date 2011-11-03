/* Handle image gallery */
/* Stripped from slimbox. http://code.google.com/p/slimbox/
   Also released under MIT license.
 */

var luffy = luffy || {};
luffy.gallery = function() {
    /* Don't run on small viewport if background-size attribute is not supported */
    if (!Modernizr.backgroundsize && $(window).width() < 900) {
	return;
    }

    var win = $(window);
    var lang = $("html").attr("lang") || "en";
    var images = $(".lf-gallery a");

    /* Options */
    var options = {
	loop: false,
	overlayOpacity: 0.8,
	overlayFadeDuration: 400,
	resizeDuration: 400,
	resizeEasing: "swing",
	initialWidth: 250,
	initialHeight: 250,
	imageFadeDuration: 400,
	captionAnimationDuration: 400,
	closeKeys: [27, 88, 67],
	previousKeys: [37, 80],
	nextKeys: [39, 78]
    };

    // Other variables
    var activeImage = -1, activeURL, prevImage, nextImage, documentElement = document.documentElement;
    var preload = {}, preloadPrev = new Image(), preloadNext = new Image();
    var overlay, center, image, sizer, prevlink, nextlink;
    var number, middle, centerWidth, centerHeight;

    /* Initialization */
    var init = function() {
	// Append the Slimbox HTML code at the bottom of the document
	$("body").append(
	    $([
		overlay = $('<div id="lfb-overlay" />')[0],
		center = $('<div id="lfb-center" />')[0],
	    ]).css("display", "none")
	);
	$('<div id="lfb-close" class="lf-sprite-slimbox-close"/>')
	    .appendTo(center).add(overlay).click(close);
	image = $('<div id="lfb-image" />').appendTo(center).append(
	    sizer = $('<div style="position: relative;" />').append([
		prevLink = $('<a id="lfb-prevlink" href="#"></a>')
		    .append($('<span id="lfb-prevlink-ico" class="lf-sprite-slimbox-left" />'))
		    .click(previous)[0],
		nextLink = $('<a id="lfb-nextlink" href="#"></a>')
		    .append($('<span id="lfb-nextlink-ico" class="lf-sprite-slimbox-right" />'))
		    .click(next)[0]
	    ])[0]
	)[0];
    };

    /* Display the indexed image */
    var slimbox = function(startImage) {
	middle = win.scrollTop() + (win.height() / 2);
	centerWidth = options.initialWidth;
	centerHeight = options.initialHeight;
	$(center).css({ top: Math.max(0, middle - (centerHeight / 2)),
			width: centerWidth,
			height: centerHeight,
			marginLeft: -centerWidth/2}).show();
	$(overlay).css("opacity", options.overlayOpacity)
	    .fadeIn(options.overlayFadeDuration);
	position();
	setup(1);
	return changeImage(startImage);
    };

    /* Bind to all images of the gallery */
    init();
    images.unbind("click").click(function() {
	var length, link = this, startImage, i = 0;
	for (length = images.length; i < length; ++i) {
	    if (images[i] == this) startImage = i;
	}
	return slimbox(startImage);
    });

    function position() {
	var l = win.scrollLeft(), w = win.width();
	$(center).css("left", l + (w / 2));
    }

    function setup(open) {
	var fn = open ? "bind" : "unbind";
	win[fn]("scroll resize", position);
	$(document)[fn]("keydown", keyDown);
	$(center)[fn]("touchstart touchmove touchend", touch);
    }

    function keyDown(event) {
	var code = event.keyCode, fn = $.inArray;
	// Prevent default keyboard action (like navigating inside the page)
	return (fn(code, options.closeKeys) >= 0) ? close()
	    : (fn(code, options.nextKeys) >= 0) ? next()
	    : (fn(code, options.previousKeys) >= 0) ? previous()
	    : false;
    }

    var touch = function () {
	var down_x = null, up_x = null;
	return function(event) {
	    if (event.type == "touchstart") {
		down_x = event.originalEvent.touches[0].pageX;
	    } else if (event.type == "touchmove") {
		event.preventDefault();
		up_x = event.originalEvent.touches[0].pageX;
	    } else {
		if (down_x - up_x > $(center).width()/3) {
		    next();
		} else if (up_x - down_x > $(center).width()/3) {
		    previous();
		}
		down_x = up_x = null;
	    }
	}
    }();

    function previous() {
	return changeImage(prevImage);
    }

    function next() {
	return changeImage(nextImage);
    }

    function changeImage(imageIndex) {
	if (imageIndex >= 0) {
	    activeImage = imageIndex;
	    activeURL = images[activeImage].href;
	    prevImage = (activeImage || (options.loop ? images.length : 0)) - 1;
	    nextImage = ((activeImage + 1) % images.length) || (options.loop ? 0 : -1);
	    stop();
	    center.className = "lfb-loading";

	    preload = new Image();
	    preload.onload = animateBox;
	    preload.src = activeURL;
	}
	return false;
    }

    function animateBox() {
	var targetWidth = preload.width, targetHeight = preload.height;
	var maxWidth = win.width() * 0.9, maxHeight = win.height() * 0.9;
	center.className = "";
	$(image).css({backgroundImage: "url(" + activeURL + ")", visibility: "hidden", display: ""});
	/* Resize the image if needed */
	if (targetWidth > maxWidth) {
	    targetHeight = targetHeight * maxWidth / targetWidth;
	    targetWidth = maxWidth;
	}
	if (targetHeight > maxHeight) {
	    targetWidth = targetWidth * maxHeight / targetHeight;
	    targetHeight = maxHeight;
	}
	$(sizer).width(targetWidth);
	$([sizer, prevLink, nextLink]).height(targetHeight);

	$(number).html((((images.length > 1) && options.counterText) || "")
		       .replace(/{x}/, activeImage + 1).replace(/{y}/, images.length));

	if (prevImage >= 0) preloadPrev.src = images[prevImage].href;
	if (nextImage >= 0) preloadNext.src = images[nextImage].href;

	centerWidth = image.offsetWidth;
	centerHeight = image.offsetHeight;
	var top = Math.max(0, middle - (centerHeight / 2));
	$(center).css({ height: centerHeight,
			width: centerWidth,
			top: top,
			marginLeft: -centerWidth/2 });
	$(image).css({ display: "none",
		       visibility: "",
		       opacity: ""}).fadeIn(options.imageFadeDuration, animateCaption);
    }

    function animateCaption() {
	if (prevImage >= 0) $(prevLink).show();
	if (nextImage >= 0) $(nextLink).show();
    }

    function stop() {
	preload.onload = null;
	preload.src = preloadPrev.src = preloadNext.src = activeURL;
	$([center, image]).stop(true);
	$([prevLink, nextLink, image]).hide();
    }

    function close() {
	if (activeImage >= 0) {
	    stop();
	    activeImage = prevImage = nextImage = -1;
	    $(center).hide();
	    $(overlay).stop().fadeOut(options.overlayFadeDuration, setup);
	}
	return false;
    }
    
};
