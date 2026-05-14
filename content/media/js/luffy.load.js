luffy.do(() => {
    const modules = [
        [".toc", "luffy1.toc.js"],
        [".codehilite", "luffy1.code.js"],
        [
            "video.lf-media source[type='application/vnd.apple.mpegurl']",
            "luffy1.videos.js",
        ],
        [".lf-gallery", "gallery.js", () => baguetteBox.run(".lf-gallery")],
        [".lf-gallery", "gallery.css"],
        // hls.js is loaded from luffy1.videos.js if needed (on Firefox mostly).
        // isso.css and isso.js are lazily loaded from luffy.comments.js
    ];
    for (const [selector, resource, onload] of modules) {
        if (document.querySelector(selector)) luffy.load(resource, onload);
    }
});
