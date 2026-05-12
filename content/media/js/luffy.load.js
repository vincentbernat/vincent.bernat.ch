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
    ];
    for (const [selector, resource, onload] of modules) {
        if (document.querySelector(selector)) luffy.load(resource, onload);
    }
});
