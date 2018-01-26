/* Change videos to embed them instead of linking to them. */

// Self-hosted HLS videos
luffy.s.push(function() {
    var videoSources = document.querySelectorAll(".lf-video source[type='application/vnd.apple.mpegurl']");
    if (videoSources.length == 0) return;

    // Check support for MSE to use with hls.js (code stolen from hls.js)
    if ((function() {
        var mediaSource = window.MediaSource || window.WebKitMediaSource;
        var sourceBuffer = window.SourceBuffer || window.WebKitSourceBuffer;
        var isTypeSupported = mediaSource &&
            typeof mediaSource.isTypeSupported === 'function' &&
            mediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E,mp4a.40.2"');
        var sourceBufferValidAPI = !sourceBuffer ||
            sourceBuffer.prototype &&
            typeof sourceBuffer.prototype.appendBuffer === 'function' &&
            typeof sourceBuffer.prototype.remove === 'function';
        return (!isTypeSupported || !sourceBufferValidAPI);
    })()) return;

    // We could also detect native HLS support but we don't want to
    // use native for broken implementation like Android. We could
    // detect native support on Safari only, but meeeh.

    // Only load hls.js if we really need it
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
