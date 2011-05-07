/* Search engine (not using Google Custome Search Engine) */

var luffy = luffy || {};
luffy.search = function() {
    /* Clicking the search glass submit the form */
    $("#lf-search-glass").click(function() {
	$("#lf-search").submit();
    });
    /* Clicking in the search box change the background to white */
    $("#lf-search-query").focus(function() {
	$(this)
	    .css("background-color", "white")
	    .css("color", "black");

    });
    $("#lf-search-query").blur(function() {
	if ($(this).val() == "") {
	    $(this)
		.css("background-color", "#666")
		.css("color", "#ccc");
	}
    });
};
