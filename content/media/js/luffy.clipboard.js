/* Add a copy to clipboard button for code blocks */

luffy.s.push(function() {
  var codeBlocks = document.querySelectorAll('main .codehilite');
  for (var i = 0; i < codeBlocks.length; i++) {
    var copyIcon = document.createElement('span');
    copyIcon.className = 'lf-sprite-copy';
    codeBlocks[i].appendChild(copyIcon);
  }

  document.body.addEventListener('click', copy, true);

  function copy(e) {
    var t = e.target;
    if (t.className === 'lf-sprite-copy') {
      // Find the el pre element
      var el = t.parentNode.childNodes[0];
      if (el.tagName === 'PRE') {
        try {
          // Ask to copy to clipboard and intercept event to force
          // text.
          function listener(e) {
            e.clipboardData.setData('text/plain', el.innerText);
            e.preventDefault();
          }
          document.addEventListener('copy', listener);
          try {
            // Try to select the text first
            if (window.getSelection) {
              el.contentEditable = true;
              el.readOnly = false;
              var selection = window.getSelection()
              var range = document.createRange();
              range.selectNodeContents(el);
              selection.removeAllRanges();
              selection.addRange(range);
              el.contentEditable = false;
              el.readOnly = false;
            }
            if (document.queryCommandEnabled("copy")) {
              document.execCommand('copy');
            } else {
              throw "Cannot copy (maybe iOS)";
            }
            selection.removeAllRanges();
            el.blur();
          } finally {
            document.removeEventListener('copy', listener);
          }
          t.className = 'lf-sprite-copy lf-copy-ok';
        } catch (err) {
          // Hint to use OS to copy
          t.className = 'lf-sprite-copy lf-copy-failed';
        }

        // Remove the message after a timeout
        setTimeout(function() { t.className = 'lf-sprite-copy'; }, 3000);
      }
    }
  }
});
