/* Change videos to embed them instead of linking to them. */

// Self-hosted HLS videos
luffy.s.push(function() {
    var videoSources = document.querySelectorAll(".lf-video source[type='application/vnd.apple.mpegurl']");
    if (videoSources.length == 0) return;

    var script = document.querySelector('script[data-name="hls.js"]');
    script.onload = function() {
        if (!Hls.isSupported()) return;

        [].forEach.call(videoSources, function(videoSource) {
            var m3u8 = videoSource.src,
                once = false,
                oldVideo = videoSource.parentNode,
                newVideo = oldVideo.cloneNode(false);

            // Replace video tag with our clone.
            oldVideo.parentNode.replaceChild(newVideo, oldVideo);

            // Pass control to hls.js
            newVideo.addEventListener('play',function() {
                if (once) return;
                var hls = new Hls({
                    capLevelToPlayerSize: true
                });
                hls.attachMedia(newVideo);
                hls.loadSource(m3u8);
                once = true;
            }, false);
        });
    };
    script.src = script.dataset.src;
});
