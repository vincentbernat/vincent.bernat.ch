// Controls for the line-breaking videos made with scratch/typo-harness. A
// video shows each combination of features one after another, for the same
// duration. Once a box is changed, the video loops over the combination
// matching the checked boxes.
luffy.do(() => {
  // Features of each video, the first one changes at each combination, the
  // second one every two combinations, and so on
  const videos = {
    "line-break/firefox": ["hyphens", "justify"],
    "line-break/chrome": ["hyphens", "justify", "pretty"],
    "line-break/webkit": ["hyphens", "justify", "pretty"],
    "line-break/preprocess": ["justify"],
  };
  const labels = {
    hyphens: "<code>hyphens: auto</code>",
    justify: "<code>text-align: justify</code>",
    pretty: "<code>text-wrap: pretty</code>",
  };
  const slowRate = 0.5;
  const duration = 3.5; // seconds for each combination
  // The last half-second of a combination does not move. Loop before its end
  // to not show the next combination when frames are reported late.
  const loop = 3.25;
  // Width of the text block over time, as in scratch/typo-harness/page.html.
  // In pixels of a 896-pixel wide frame, the block starts after a padding of
  // 24 pixels.
  const sweep = {
    frame: 896,
    padding: 24,
    from: 770,
    grow: 0.1,
    hold: 1,
    length: 2,
    before: 20, // pointer reacting before the narrowest width
  };

  // Time in a combination when the text block has this width. The width
  // follows a smoothstep, its inverse is 1/2 - sin(asin(1 - 2y) / 3).
  const timeAt = (width) => {
    const y = Math.min(1, Math.max(0, (width / sweep.from - 1) / sweep.grow));
    const x = 0.5 - Math.sin(Math.asin(1 - 2 * y) / 3);
    return sweep.hold + sweep.length * x;
  };

  // All the videos, to pause the others while the pointer is over one
  const players = [];

  for (const video of document.querySelectorAll("video.lf-media")) {
    const src = video.currentSrc || video.src;
    const name = Object.keys(videos).find((n) => src.includes(`/${n}.`));
    if (!name) continue;
    const features = videos[name];
    const count = 1 << features.length;
    video.controls = false;

    const controls = document.createElement("div");
    controls.className = "lf1-video-features";
    const checkbox = (html) => {
      const label = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox";
      label.append(box);
      label.insertAdjacentHTML("beforeend", html);
      controls.append(label);
      return box;
    };
    const boxes = features.map((feature) => checkbox(labels[feature]));
    const slow = checkbox(`${slowRate}× speed`);
    slow.parentElement.className = "lf1-video-speed";
    slow.addEventListener("change", () => {
      video.playbackRate = slow.checked ? slowRate : 1;
    });
    const outer = video.closest(".lf-media-outer") || video;
    // As wide as the video
    controls.style.width = outer.style.width;
    outer.after(controls);

    // Until a feature is checked, the video plays all combinations and the
    // boxes follow it
    let all = true;

    const play = () => {
      const playing = video.play();
      if (playing) playing.catch(() => {});
    };
    let hovering = false;
    let start = 0;
    let seeking = false;
    const seek = (time) => {
      seeking = true;
      video.currentTime = time;
    };
    // Select the combination at this time
    const select = (time) => {
      const index = Math.min(Math.floor(time / duration), count - 1);
      start = index * duration;
      boxes.forEach((box, i) => (box.checked = (index >> i) & 1));
    };
    const check = (time) => {
      if (all) select(time);
      else if (time < start || time >= start + loop) seek(start);
    };

    boxes.forEach((box) =>
      box.addEventListener("change", () => {
        all = false;
        const index = boxes.reduce((n, b, i) => n | (b.checked << i), 0);
        start = index * duration;
        seek(start);
        if (!hovering) play();
      }),
    );

    // Over the video, pause it and the others. From the narrowest position of
    // the right edge of the text block to the right of the video, show the
    // frame where the edge is under the pointer.
    const player = { video, play, held: false };
    players.push(player);
    const enter = () => {
      if (hovering) return;
      hovering = true;
      video.pause();
      // Safari flickers when another video plays at the same time
      for (const other of players) {
        if (other === player || other.video.paused) continue;
        other.held = true;
        other.video.pause();
      }
    };
    const leave = () => {
      if (!hovering) return;
      hovering = false;
      target = null;
      play();
      for (const other of players) {
        if (!other.held) continue;
        other.held = false;
        other.play();
      }
    };
    // At most one seek for each frame, to the last position of the pointer.
    // A seek still running delays the next one.
    let target = null;
    let scheduled = false;
    const follow = () => {
      scheduled = false;
      if (!hovering || seeking || target === null) return;
      seek(target);
      target = null;
    };
    video.addEventListener("mouseenter", enter);
    video.addEventListener("mousemove", (event) => {
      enter();
      // The video may be shrunk, use the position as a part of its width
      const rect = video.getBoundingClientRect();
      const ratio = (event.clientX - rect.left) / rect.width;
      const width = ratio * sweep.frame - sweep.padding;
      if (width < sweep.from - sweep.before) return;
      target = start + timeAt(width);
      if (!scheduled) {
        scheduled = true;
        requestAnimationFrame(follow);
      }
    });
    video.addEventListener("mouseleave", leave);

    // Another seek, like the loop to the start, selects the combination at
    // this time
    video.addEventListener("seeking", () => {
      if (!seeking) select(video.currentTime);
    });
    video.addEventListener("seeked", () => {
      seeking = false;
      if (target !== null && !scheduled) {
        scheduled = true;
        requestAnimationFrame(follow);
      }
    });

    // Not metadata.mediaTime: once the video loops, Firefox keeps the time of
    // the last frame before the loop
    const update = () => check(video.currentTime);
    if ("requestVideoFrameCallback" in video) {
      const frame = () => {
        update();
        video.requestVideoFrameCallback(frame);
      };
      video.requestVideoFrameCallback(frame);
    } else {
      video.addEventListener("timeupdate", update);
    }
  }
});
