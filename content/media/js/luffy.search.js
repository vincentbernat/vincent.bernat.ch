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
	if ($(this).val() === "") {
	    $(this)
		.css({"background-color": "#666",
		      color: "#ccc"});
	}
    });

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

    /* Submit request to Microsoft Bing */
    $("#lf-search").submit(function(event) {
	var AppId = "92F36BFCB584BE6F156D5AD0C4487D0585FF6E7A";
	var query = $("#lf-search-query").val();
	var lang = $("html").attr("lang");
	var market = (lang === "fr")?"fr-FR":"en-US";
	event.preventDefault();
	if (query === "") return;
	var requestStr = "http://api.bing.net/json.aspx?"
	    + "AppId=" + AppId
	    + "&Query=site:vincent.bernat.im/" + lang
	    + "%20" + encodeURIComponent(query)
	    + "&Sources=Web"
	    + "&Version=2.0"
	    + "&Market=" + market
	    + "&Options=EnableHighlighting"
	    + "&Web.Count=10"
	    + "&Web.Offset=0"
	    + "&JsonType=callback"
	    + "&JsonCallback=?";
	$.ajax({
	    url: requestStr,
	    dataType: 'jsonp',
	    success: function(data) {
		if (!data || !data.SearchResponse || data.SearchResponse.Errors) {
		    $("#lf-search").submit(); // Fallback to classic search
		    return;
		}
		var wresults = data.SearchResponse.Web.Results;
		var ul = $("<div class='zero'>:-(</div>");
		var bold = function(text) {
		    return $('<i/>').text(text).html()
			.replace(/\uE000/g, "<strong>")
			.replace(/\uE001/g, "</strong>");
		}
		show();
		if (wresults) {
		    ul = $("<ul></ul>");
		    for (var i = 0; i < wresults.length ; i++) {
			/* Drop the part after `|' in the title */
			var title = bold(wresults[i].Title.split(" | ")[0]);
			var descr = bold(wresults[i].Description);
			ul.append($("<li></li>").append(
			    $("<a></a>")
				.attr("href", wresults[i].Url)
				.html(title),
			    $("<time></time>")
				.text(jQuery.timeago(wresults[i].DateTime)),
			    $("<span></span>").html(descr)
			));
		    }
		}
		results.append(ul);
	    }
	});
    });
};
