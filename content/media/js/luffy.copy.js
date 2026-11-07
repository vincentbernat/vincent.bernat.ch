/* Remove soft hyphens, zero-width and no-break spaces from copied text */

luffy.do(() => {
  document.addEventListener("copy", (event) => {
    const selection = document.getSelection();
    const raw = selection.toString();
    const text = raw
      // SOFT HYPHEN, ZERO WIDTH SPACE
      .replace(/[\u00ad\u200b]/g, "")
      // NO-BREAK SPACE, NARROW NO-BREAK SPACE
      .replace(/[\u00a0\u202f]/g, " ");
    if (text === raw) return;
    const div = document.createElement("div");
    for (let i = 0; i < selection.rangeCount; i++)
      div.appendChild(selection.getRangeAt(i).cloneContents());
    event.clipboardData.setData("text/plain", text);
    event.clipboardData.setData("text/html", div.innerHTML);
    event.preventDefault();
  });
});
