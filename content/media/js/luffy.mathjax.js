/* Run KaTeX */

luffy.s.push(function() {
  // KaTeX rendering. Assuming it is loaded.
  if (typeof window.renderMathInElement !== "function") return;
  window.renderMathInElement(document.body, {
    delimiters: [{left: "··", right: "··", display: true},
                 {left: "·", right: "·", display: false}]
  });
});
