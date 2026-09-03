/* Add a copy to clipboard button for code blocks */

luffy.do(() => {
  if (!navigator.clipboard) return;

  const label = document.documentElement.lang.startsWith("fr")
    ? "Copier vers le presse-papier"
    : "Copy to clipboard";

  // Get the text of a code block.
  const codeText = (node) => {
    if (node.nodeType === Node.TEXT_NODE) return node.nodeValue;
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    if (getComputedStyle(node).userSelect === "none") return "";
    let text = "";
    for (const child of node.childNodes) text += codeText(child);
    return text;
  };

  for (const block of document.querySelectorAll(".lf-main .codehilite")) {
    const pre = block.querySelector("pre");
    if (!pre) continue;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "lf-copy";
    button.setAttribute("aria-label", label);

    // Tell the user if the copy worked.
    let timer;
    const showMessage = (name) => {
      clearTimeout(timer);
      button.classList.remove("msg-copy-ok", "msg-copy-failed");
      button.classList.add(name);
      timer = setTimeout(() => button.classList.remove(name), 3000);
    };

    button.addEventListener("click", () => {
      navigator.clipboard.writeText(codeText(pre)).then(
        () => showMessage("msg-copy-ok"),
        () => showMessage("msg-copy-failed"),
      );
    });
    block.appendChild(button);
  }
});
