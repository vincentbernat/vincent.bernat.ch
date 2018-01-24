/* Change videos to embed them instead of linking to them. */

luffy.s.push(function() {
    if (typeof document.querySelectorAll !== "function") return;
    if (typeof window.Hls !== "function") return;

    // Self-hosted HLS videos
    var videoSources = document.querySelectorAll(".lf-video source[type='application/vnd.apple.mpegurl']");
    if(Hls.isSupported()) {
        [].forEach.call(videoSources, function(videoSource) {
            // We assume preload="none"
            var hls = new Hls({
                autoStartLoad: false,
                capLevelToPlayerSize: true
            }),
                m3u8 = videoSource.src,
                oldVideo = videoSource.parentNode,
                newVideo = oldVideo.cloneNode(false);

            // Replace video tag with our clone.
            oldVideo.parentNode.replaceChild(newVideo, oldVideo);

            // Pass control to hls.js
            hls.attachMedia(newVideo);
            hls.loadSource(m3u8);
            newVideo.addEventListener('play',function() {
                hls.startLoad();
            });
        });
    }
});
