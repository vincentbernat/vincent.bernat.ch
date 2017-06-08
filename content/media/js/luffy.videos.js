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
                id = this.href.match(/v=(.*)$/)[1];
            iframe.className = "lf-video";
            iframe.setAttribute("allowfullscreen", "");
            iframe.setAttribute("src",
                                "https://www.youtube-nocookie.com/embed/" + id + "?rel=0&autoplay=1");
            this.parentNode.appendChild(iframe);
            this.parentNode.removeChild(this);
        });
    }

    // Note: we try to use autoplay, but on mobile, autoplay won't
    // work unless the video is muted. Safari on iOS 11 is a bit more
    // leniant, also allowing autoplay when there is no sound
    // track. YT doesn't allow to set the muted tag using an URL
    // parameter, so the video won't autoplay on mobile: the user has
    // to click twice.
};
