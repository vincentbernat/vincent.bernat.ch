// Self-hosted videos with HLS
luffy.do(() => {
  const hlsSource = "source[type='application/vnd.apple.mpegurl']";
  const hlsVideos = [
    ...document.querySelectorAll(`video.lf-media ${hlsSource}`),
  ].map(({ parentNode }) => parentNode);
  if (hlsVideos.length === 0) return;

  // Enable HLS for selected videos
  luffy.load("hls.js", () => {
    if (Hls.isSupported()) {
      hlsVideos.forEach((oldVideo, index) => {
        const m3u8 = oldVideo.querySelector(hlsSource).src;
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
        hls.on(Hls.Events.AUDIO_TRACKS_UPDATED, () => {
          // Switch audio track to match the document language
          const track = hls.audioTracks.find(
            ({ lang }) =>
              lang?.slice(0, 2) === document.documentElement.lang.slice(0, 2),
          );
          if (track) hls.audioTrack = track.id;
        });
        hls.loadSource(m3u8);
        hls.attachMedia(newVideo);
        newVideo.addEventListener(
          "play",
          () => hls.startLoad(newVideo.currentTime),
          false,
        );

        hlsVideos[index] = newVideo;
        oldVideo.parentNode.replaceChild(newVideo, oldVideo);
      });
    }

    hlsVideos.forEach((video) => {
      // Pause other videos when playing a new one
      video.addEventListener(
        "play",
        ({ target }) => {
          hlsVideos.forEach((ovideo) => {
            if (target !== ovideo && !ovideo.paused) ovideo.pause();
          });
        },
        false,
      );
      // Count for analytics, only on the first play
      video.addEventListener(
        "play",
        () => luffy.count?.({ event: "play-video", title: "Play a video" }),
        { once: true },
      );
    });
  });
});

// Make seek-to links work
luffy.do(() => {
  const seekLinks = document.querySelectorAll("a[href^='#video:seek-']");
  seekLinks.forEach((seekLink) => {
    seekLink.addEventListener("click", (event) => {
      event.preventDefault();

      const seekTo = parseInt(seekLink.hash.slice(12), 10);
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
