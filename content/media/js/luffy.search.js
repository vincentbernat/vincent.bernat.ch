/* Search engine */

var luffy = luffy || {};
luffy.search = function() {
    var panel = $("#lf-search-results");
    var results = $("#lf-search-results-results")

    /* Hide and close search result panel */
    var close = function() {
	if (!panel.is(":visible")) return;
	panel.animate({left: "-150%"}, 500, function() {
	    panel.hide();
	});
    };
    /* Show panel */
    var show = function() {
	results.html("");
	panel.show().animate({left: "0%"}, 500);
    }
    $("#lf-search-results-close").bind("click", close);
    $(document).bind("keydown", function(event) {
	if (event.keyCode === 27) close();
	return true;
    });

    /* Submit request to Google Search */
    $("#lf-search").submit(function(event) {
	var apikey = "AIzaSyBYIVw9Z98BD2xgc9IdKo8-tJMmyUJhGAs";
	var cse = "005302691838508801550:am84wi88jr8";
	var query = $("#lf-search-query").val();
	var lang = $("html").attr("lang");
	event.preventDefault();
	if (query === "") return;
	var requestStr = "https://www.googleapis.com/customsearch/v1?"
	    + "&key=" + apikey
	    + "&cx=" + cse
	    + "&lr=lang_" + lang
	    + "&q=" + encodeURIComponent(query);
	$.ajax({
	    url: requestStr,
	    dataType: 'jsonp',
	    error: function() {
		$("#lf-search")
		    .unbind('submit')
		    .submit(); // Fallback to classic search
	    },
	    success: function(data) {
		var wresults = data.items;
		var ul = $("<div class='zero'>:-(</div>");
		show();
		if (wresults) {
		    ul = $("<ul></ul>");
		    for (var i = 0; i < wresults.length ; i++) {
			/* Drop the part after `|' in the title */
			var title = wresults[i].htmlTitle.split(" | ")[0];
			var descr = wresults[i].htmlSnippet;
			ul.append($("<li></li>").append(
			    $("<a></a>")
				.attr("href", wresults[i].link)
				.html(title),
			    $("<div></div>").addClass("snippet").html(descr),
			    $("<div></div>").addClass("url")
				.text(wresults[i]
				      .link.replace("http://", ""))
			));
		    }
		}
		results.append(ul);
	    }
	});
    });
};
