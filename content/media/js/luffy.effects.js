/* Some simple effects when the site is loaded. */

var luffy = luffy || {};
luffy.effects = function() {
    var e;

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
