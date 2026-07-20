// Self-hosted videos
luffy.do(() => {
  // Pause other videos when playing a new one
  const allVideos = (selector) => {
    selector = selector || "";
    return document.querySelectorAll(`video.lf-media ${selector}`);
  };
  const pauseOthersWhenPlaying = (video) => {
    video.addEventListener(
      "play",
      ({ target }) => {
        allVideos().forEach((ovideo) => {
          if (target != ovideo && !ovideo.paused) ovideo.pause();
        });
      },
      false,
    );
  };
  allVideos().forEach(pauseOthersWhenPlaying);

  const videoSources = document.querySelectorAll(
    "video.lf-media source[type='application/vnd.apple.mpegurl']",
  );
  if (videoSources.length == 0) return;

  // Enable HLS for selected videos
  luffy.load("hls.js", () => {
    if (!Hls.isSupported()) return;

    videoSources.forEach(({ src, parentNode }) => {
      const m3u8 = src;
      const oldVideo = parentNode;
      const newVideo = oldVideo.cloneNode(true);
      const allSources = newVideo.querySelectorAll("source");

      // Remove all sources from clone. Keep tracks.
      allSources.forEach((source) => source.remove());

      // Enable HLS on the video
      const hls = new Hls({
        autoStartLoad: false,
        capLevelToPlayerSize: true,
        maxMaxBufferLength: 90,
      });
      hls.loadSource(m3u8);
      hls.attachMedia(newVideo);
      newVideo.addEventListener(
        "play",
        () => hls.startLoad(newVideo.currentTime),
        false,
      );
      pauseOthersWhenPlaying(newVideo);

      // Replace video tag with our clone.
      oldVideo.parentNode.replaceChild(newVideo, oldVideo);
    });
  });
});

// Make seek-to links work
luffy.do(() => {
  const seekLinks = document.querySelectorAll("a[href^='#video:seek-']");
  seekLinks.forEach((seekLink) => {
    seekLink.addEventListener("click", (event) => {
      event.preventDefault();

      const seekTo = parseInt(seekLink.hash.substr(12), 10);
      const videos = document.querySelectorAll("video");

      // Look for the nearest video before that
      for (let i = videos.length - 1; i >= 0; i--) {
        if (
          seekLink.compareDocumentPosition(videos[i]) &
          Node.DOCUMENT_POSITION_PRECEDING
        ) {
          videos[i].currentTime = seekTo;
          if (videos[i].paused) videos[i].play();

          // Scroll element into view if needed
          const rect = videos[i].getBoundingClientRect();
          if (
            rect.top >= 0 &&
            rect.bottom <=
              (window.innerHeight || document.documentElement.clientHeight)
          )
            break;
          videos[i].scrollIntoView();
          break;
        }
      }
    });
  });
});
