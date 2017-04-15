var luffy = luffy || {};
luffy.mathjax = function() {
  // KaTeX rendering. Assuming it is loaded.
  if (typeof window.renderMathInElement !== "function") return;
  renderMathInElement(document.body, {
    delimiters: [{left: "··", right: "··", display: true},
                 {left: "·", right: "·", display: false}]
  });
};
