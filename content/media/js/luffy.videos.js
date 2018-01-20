/* Change videos to embed them instead of linking to them. */

luffy.s.push(function() {
    if (typeof document.querySelectorAll !== "function") return;

    // Self-hosted HLS videos
    var hls_videos = document.querySelectorAll(".lf-video[src$='.m3u8']");
    if (hls_videos.length > 0) {
        if(Hls.isSupported()) {
            for (var i = 0; i < hls_videos.length; i++) {
                var hls = new Hls();
                var video = hls_videos[i];
                hls.loadSource(video.src);
                hls.attachMedia(video);
            }
        }
    }
});
