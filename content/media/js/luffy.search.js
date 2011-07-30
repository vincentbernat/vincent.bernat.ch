/* Search engine */

var luffy = luffy || {};
luffy.search = function() {
    /* Clicking in the search box change the background to white */
    $("#lf-search-query").focus(function() {
	$(this)
	    .css({"background-color": "white",
		  color: "black"});

    });
    $("#lf-search-query").blur(function() {
	if ($(this).val() == "") {
	    $(this)
		.css({"background-color": "#666",
		      color: "#ccc"});
	}
    });
};
