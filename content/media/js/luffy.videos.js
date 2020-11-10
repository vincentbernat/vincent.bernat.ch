luffy.s.push(function() {
    if (!document.querySelector("video")) return;
    luffy.load("hls.js", function() {
        luffy.load("luffy1.videos.js");
    });
});
