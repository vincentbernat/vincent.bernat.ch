// Self-hosted videos
luffy.do(function() {
    var videoSources = document.querySelectorAll("video.lf-media source[type='application/vnd.apple.mpegurl']");
    if (videoSources.length == 0) return;

    // Enable HLS for selected videos
    luffy.load("hls.js", function() {
        if (!Hls.isSupported()) return;

        [].forEach.call(videoSources, function(videoSource) {
            var m3u8 = videoSource.src,
                once = false,
                oldVideo = videoSource.parentNode,
                newVideo = oldVideo.cloneNode(true),
                allSources = newVideo.querySelectorAll('source'); // ":scope > source" is not well-supported

            // Remove all sources from clone. Keep tracks.
            [].forEach.call(allSources, function(source) {
                source.remove();
            });

            // Add an empty source (enable play event on Chromium 72+)
            newVideo.src = "about:blank";

            // Replace video tag with our clone.
            oldVideo.parentNode.replaceChild(newVideo, oldVideo);

            // Pass control to hls.js
            var play = function() {
                if (once) return;
                var hls = new Hls({
                    capLevelToPlayerSize: true,
                    maxMaxBufferLength: 90
                });
                hls.loadSource(m3u8);
                hls.attachMedia(newVideo);
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    newVideo.play();
                });
                once = true;
            };
            newVideo.addEventListener('play', play, false);
        });
    });
});

// Make seek-to links work
luffy.do(function() {
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

                    // Scroll element into view if needed
                    var rect = videos[i].getBoundingClientRect();
                    if (rect.top >= 0 &&
                        rect.bottom <= (window.innerHeight ||
                                       document.documentElement.clientHeight))
                        break;
                    videos[i].scrollIntoView();
                    break;
                }
            }
        });
    });
});
