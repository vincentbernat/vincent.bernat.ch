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
      // Find the sibling pre element
      var sibling = t.parentNode.childNodes[0];
      if (sibling.tagName === 'PRE') {
        try {
          // Ask to copy to clipboard and intercept event to force
          // text.
          function listener(e) {
            e.clipboardData.setData('text/plain', sibling.innerText);
            e.preventDefault();
          }
          document.addEventListener('copy', listener);
          try {
            document.execCommand('copy');
          } finally {
            document.removeEventListener('copy', listener);
          }
          t.className = 'lf-sprite-copy lf-copy-ok';
        } catch (err) {
          // Try to select the text instead
          if (window.getSelection) {
            var selection = window.getSelection()
            var range = document.createRange();
            range.selectNodeContents(sibling);
            selection.removeAllRanges();
            selection.addRange(range);
          }
          // Hint to use OS to copy
          t.className = 'lf-sprite-copy lf-copy-failed';
        }

        // Remove the message after a timeout
        setTimeout(function() { t.className = 'lf-sprite-copy'; }, 3000);
      }
    }
  }
});
