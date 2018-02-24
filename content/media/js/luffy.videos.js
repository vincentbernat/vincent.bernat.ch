// Self-hosted videos
luffy.s.push(function() {
    var videoSources = document.querySelectorAll(".lf-video source[type='application/vnd.apple.mpegurl']");
    if (videoSources.length == 0) return;

    // Enable HLS for selected videos
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
            newVideo.addEventListener('play', function() {
                if (once) return;
                var hls = new Hls({
                    capLevelToPlayerSize: true,
                    maxMaxBufferLength: 90
                });
                hls.attachMedia(newVideo);
                hls.loadSource(m3u8);
                once = true;
            }, false);
        });
    };
    script.src = script.dataset.src;
});

// Make seek-to links work
luffy.s.push(function() {
    var seekLinks = document.querySelectorAll("a[href^='#video-seek-']");
    [].forEach.call(seekLinks, function(seekLink) {
        seekLink.addEventListener('click', function(event) {
            event.preventDefault();

            var seekTo = parseInt(seekLink.hash.substr(12), 10),
                videos = document.querySelectorAll("video");

            // Look for the nearest video before that
            for (var i = videos.length - 1; i >= 0; i--) {
                if (seekLink.compareDocumentPosition(videos[i]) &
                    Node.DOCUMENT_POSITION_PRECEDING) {
                    videos[i].currentTime = seekTo;
                    if (videos[i].paused) videos[i].play();
                    break;
                }
            }
        });
    });
});
