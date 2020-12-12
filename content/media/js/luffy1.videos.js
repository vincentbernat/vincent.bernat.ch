// Self-hosted videos
luffy.do(() => {
    // Pause other videos when playing a new one
    const allVideos = (selector) => {
        selector = selector || "";
        return document.querySelectorAll("video.lf-media " + selector);
    }
    const pauseOthers = (event) => {
        const others = allVideos();
        others.forEach((video) => {
            if (event.target != video && !video.paused)
                video.pause();
        });
    };
    allVideos().forEach((video) => video.addEventListener('play', pauseOthers, false));

    const videoSources = document.querySelectorAll("video.lf-media source[type='application/vnd.apple.mpegurl']");
    if (videoSources.length == 0) return;

    // Enable HLS for selected videos
    luffy.load("hls.js", () => {
        if (!Hls.isSupported()) return;

        videoSources.forEach(({src, parentNode}) => {
            let once = false;
            const m3u8 = src; // ":scope > source" is not well-supported
            const oldVideo = parentNode;
            const newVideo = oldVideo.cloneNode(true);
            const allSources = newVideo.querySelectorAll('source');

            // Remove all sources from clone. Keep tracks.
            allSources.forEach(source => source.remove());

            // Add an empty source (enable play event on Chromium 72+)
            newVideo.src = "about:blank";

            // Replace video tag with our clone.
            oldVideo.parentNode.replaceChild(newVideo, oldVideo);

            // Pass control to hls.js
            const play = () => {
                if (once) return;
                const hls = new Hls({
                    capLevelToPlayerSize: true,
                    maxMaxBufferLength: 90
                });
                hls.loadSource(m3u8);
                hls.attachMedia(newVideo);
                hls.on(Hls.Events.MANIFEST_PARSED, () => {
                    newVideo.play();
                });
                once = true;
            };
            newVideo.addEventListener('play', play, false);
            newVideo.addEventListener('play', pauseOthers, false);
        });
    });
});

// Make seek-to links work
luffy.do(() => {
    const seekLinks = document.querySelectorAll("a[href^='#video-seek-']");
    seekLinks.forEach(seekLink => {
        seekLink.addEventListener('click', event => {
            event.preventDefault();

            const seekTo = parseInt(seekLink.hash.substr(12), 10);
            const videos = document.querySelectorAll("video");

            // Look for the nearest video before that
            for (let i = videos.length - 1; i >= 0; i--) {
                if (seekLink.compareDocumentPosition(videos[i]) &
                    Node.DOCUMENT_POSITION_PRECEDING) {
                    videos[i].currentTime = seekTo;
                    if (videos[i].paused) videos[i].play();

                    // Scroll element into view if needed
                    const rect = videos[i].getBoundingClientRect();
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
