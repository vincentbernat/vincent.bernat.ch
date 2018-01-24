/* Change videos to embed them instead of linking to them. */

luffy.s.push(function() {
    if (typeof document.querySelectorAll !== "function") return;

    // Self-hosted HLS videos
    var hls_videos = document.querySelectorAll(".lf-video source[type='application/vnd.apple.mpegurl']");
    if(Hls.isSupported()) {
        [].forEach.call(hls_videos, function(video) {
            // We assume preload="none"
            var hls = new Hls({
                autoStartLoad: false,
                capLevelToPlayerSize: true
            }),
                m3u8 = video.src;
            // Remove all sources
            video = video.parentNode;
            while (video.hasChildNodes()) {
                video.removeChild(video.lastChild);
            }
            // Pass control to hls.js
            hls.attachMedia(video);
            hls.loadSource(m3u8);
            video.addEventListener('play',function() {
                hls.startLoad();
            });
        });
    }
});
