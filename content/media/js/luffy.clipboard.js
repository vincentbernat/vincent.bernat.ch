/* Add a copy to clipboard button for code blocks */

luffy.do(() => {
  if (!window.getSelection) {
    return;
  }

  const codeBlocks = document.querySelectorAll('.lf-main .codehilite');
  for (let i = 0; i < codeBlocks.length; i++) {
    const copyIcon = document.createElement('span');
    copyIcon.className = 'lf-copy';
    codeBlocks[i].appendChild(copyIcon);
  }

  document.body.addEventListener('click', copy, true);

  function copy({target}) {
    const t = target;
    if (t.className === 'lf-copy') {
      // Find the sibling pre element
      const el = t.parentNode.childNodes[0];
      if (el.tagName === 'PRE') {
        try {
          // Select text
          t.blur();
          el.contentEditable = true;
          el.readOnly = false;
          const selection = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(el);
          selection.removeAllRanges();
          selection.addRange(range);
          el.contentEditable = false;
          el.readOnly = false;

          // Copy
          if (document.queryCommandEnabled("copy")) {
            document.execCommand('copy');
          } else {
            throw "Cannot copy (maybe iOS)";
          }

          // Unselect
          selection.removeAllRanges();
          el.blur();

          // Inform user
          t.className = 'msg-copy-ok lf-copy';
        } catch (err) {
          // Hint to use OS to copy
          t.className = 'msg-copy-failed lf-copy';
        }

        // Remove the message after a timeout
        setTimeout(() => { t.className = 'lf-copy'; }, 3000);
      }
    }
  }
});
