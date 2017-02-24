/* Add captions to images. */

var luffy = luffy || {};
luffy.videos = function() {
    if (typeof document.querySelectorAll !== "function") return;

    // Youtube videos
    var youtube = document.querySelectorAll(".lf-video[href^='https://www.youtube.com/watch']");
    for (var i = 0; i < youtube.length; i++) {
        youtube[i].addEventListener("click", function(event) {
            event.preventDefault();
            var iframe = document.createElement("iframe"),
                div = document.createElement("div"),
                id = this.href.match(/v=(.*)$/)[1];
            div.className = "lf-video";
            iframe.setAttribute("allowfullscreen", "");
            iframe.setAttribute("src",
                                "https://www.youtube.com/embed/" + id + "?rel=0&autoplay=1");
            div.appendChild(iframe);
            this.parentNode.appendChild(div);
            this.parentNode.removeChild(this);
        });
    }
};
