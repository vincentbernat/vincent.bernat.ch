/* Add a copy to clipboard button for code blocks */

luffy.do(function() {
  if (!window.getSelection) {
    return;
  }

  var codeBlocks = document.querySelectorAll('.lf-main .codehilite');
  for (var i = 0; i < codeBlocks.length; i++) {
    var copyIcon = document.createElement('span');
    copyIcon.className = 'lf-sprite-copy';
    codeBlocks[i].appendChild(copyIcon);
  }

  document.body.addEventListener('click', copy, true);

  function copy(e) {
    var t = e.target;
    if (t.className === 'lf-sprite-copy') {
      // Find the sibling pre element
      var el = t.parentNode.childNodes[0];
      if (el.tagName === 'PRE') {
        try {
          // Select text
          t.blur();
          el.contentEditable = true;
          el.readOnly = false;
          var selection = window.getSelection()
          var range = document.createRange();
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
          t.className = 'msg-copy-ok lf-sprite-copy';
        } catch (err) {
          // Hint to use OS to copy
          t.className = 'msg-copy-failed lf-sprite-copy';
        }

        // Remove the message after a timeout
        setTimeout(function() { t.className = 'lf-sprite-copy'; }, 3000);
      }
    }
  }
});
