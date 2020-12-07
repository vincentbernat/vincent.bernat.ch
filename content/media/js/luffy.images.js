luffy.do(function() {
  /* When opaque images are loaded, change their background to
   * transparent. Otherwise, if they are ratio restricted, notably
   * vertically, the shadow will be around the background. */
  var loaded = function() {
    this.style.backgroundColor = "transparent";
  };
  [].forEach.call(document.querySelectorAll(".lf-opaque"), function(img) {
    img.onload = loaded;
    if (img.complete) {
      loaded.call(img);
    }
  });
});
