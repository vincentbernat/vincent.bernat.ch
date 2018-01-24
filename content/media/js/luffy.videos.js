/* Change videos to embed them instead of linking to them. */

luffy.s.push(function() {
    if (typeof document.querySelectorAll !== "function") return;

    // Self-hosted HLS videos
    var hls_videos = document.querySelectorAll(".lf-video source[type='application/vnd.apple.mpegurl']");
    if(Hls.isSupported()) {
        for (var i = 0; i < hls_videos.length; i++) {
            // We assume preload="none"
            var hls = new Hls({
                autoStartLoad: false,
                capLevelToPlayerSize: true
            }),
                video = hls_videos[i],
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
            hls.on(Hls.Events.ERROR, function (event, data) {
                if (data.fatal) {
                    switch(data.type) {
                    case Hls.ErrorTypes.NETWORK_ERROR:
                        console.log("HLS: fatal network error encountered, try to recover",
                                    data.details);
                        hls.startLoad();
                        break;
                    case Hls.ErrorTypes.MEDIA_ERROR:
                        console.log("HLS: fatal media error encountered, try to recover",
                                   data.details);
                        hls.recoverMediaError();
                        break;
                    default:
                        console.log("HLS: unrecoverable fatal media error encountered",
                                    data.type, data.details);
                        hls.destroy();
                        break;
                    }
                }
            });
        }
    }
});
