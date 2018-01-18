/* Turn footnotes to sidenotes. */

luffy.s.push(function() {
  if (typeof document.querySelectorAll !== "function") return;
  var footnotes = document.querySelector("#lf-text .footnote ol"),
  footnoteReferences = document.querySelectorAll("#lf-text sup[id^=fnref-]"),
  i;
  for (i = 0; i < footnoteReferences.length; i++) {
    var footnoteReference = footnoteReferences[i],
    footnoteName = footnoteReference.id.replace(/^fnref-/, ''),
    footnote = footnotes.querySelector("li[id=fn-" + footnoteName + "]");
    /* Search for suitable parent and attach the side-note to it */
    var sidenote = document.createElement("aside"),
        parent = footnoteReference.parentNode;
    while (parent &&
           parent.parentNode &&
           parent.parentNode.id != "lf-text") {
      parent = parent.parentNode;
    }
    if (!parent || !footnote) {
      throw new Error("footnote `" + footnoteName + "' not found");
    }
    sidenote.setAttribute("role", "note");
    sidenote.className = "lf-sidenote";
    sidenote.innerHTML =
      "<sup class=\"lf-refmark\">" + footnoteReference.innerText + "</sup>"
      + footnote.innerHTML; // No ID, we don't want to shadow the original one
    parent.parentNode.insertBefore(sidenote, parent);
  }
  document.body.className += ' lf-has-sidenotes';
});
