// Self-hosted videos with HLS, played by Video.js
luffy.do(() => {
  const hlsSource = "source[type='application/vnd.apple.mpegurl']";
  const hlsVideos = [
    ...document.querySelectorAll(`video.lf-media ${hlsSource}`),
  ].map(({ parentNode }) => parentNode);
  if (hlsVideos.length === 0) return;

  // Video.js 10 needs MSE and a recent browser (the most recent feature it uses
  // is CSS nesting).
  const mse = window.MediaSource || window.ManagedMediaSource;
  if (!mse || !window.CSS?.supports("selector(&)")) return;

  const language = document.documentElement.lang.slice(0, 2);

  luffy.load("videojs.js", () => {
    const videos = hlsVideos.map((oldVideo) => {
      // <media-i18n> takes the language from the document, <video-player>
      // owns the state, <video-minimal-skin> draws the controls.
      const i18n = document.createElement("media-i18n");
      const player = document.createElement("video-player");
      const skin = document.createElement("video-minimal-skin");
      const video = document.createElement("hls-video");

      skin.className = oldVideo.className;
      player.setAttribute("poster", oldVideo.poster);
      video.setAttribute("playsinline", "");
      video.setAttribute("crossorigin", oldVideo.crossOrigin);
      video.setAttribute("preload", oldVideo.preload);
      video.setAttribute("src", oldVideo.querySelector(hlsSource).src);
      video.append(...oldVideo.querySelectorAll("track"));
      video.querySelector("track[kind=chapters]")?.setAttribute("default", "");

      // Switch audio track to match the document language. The tracks are
      // added one by one, wait for the whole list before choosing.
      video.audioTracks.addEventListener(
        "addtrack",
        () =>
          queueMicrotask(() => {
            const track = [...video.audioTracks].find(
              (audio) => audio.language?.slice(0, 2) === language,
            );
            if (track) track.enabled = true;
          }),
        { once: true },
      );

      // Drop the picture-in-picture button.
      skin.shadowRoot.querySelector("media-pip-button")?.remove();

      skin.append(video);
      player.append(skin);
      i18n.append(player);
      oldVideo.replaceWith(i18n);
      return video;
    });

    videos.forEach((video) => {
      // Pause other videos when playing a new one
      video.addEventListener(
        "play",
        ({ target }) => {
          videos.forEach((ovideo) => {
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
      const videos = document.querySelectorAll("video, hls-video");

      // Look for the nearest video before that
      for (let i = videos.length - 1; i >= 0; i--) {
        if (
          seekLink.compareDocumentPosition(videos[i]) &
          Node.DOCUMENT_POSITION_PRECEDING
        ) {
          videos[i].currentTime = seekTo;
          if (videos[i].paused) videos[i].play();

          // Scroll element into view if needed. An <hls-video> has no box of
          // its own, the skin around it has one.
          const box = videos[i].closest("video-minimal-skin") ?? videos[i];
          const rect = box.getBoundingClientRect();
          if (
            rect.top >= 0 &&
            rect.bottom <=
              (window.innerHeight || document.documentElement.clientHeight)
          )
            break;
          box.scrollIntoView();
          break;
        }
      }
    });
  });
});
