# Typography harness

Videos of the Verne paragraph of `content/en/blog/wip.html` in Firefox,
Chromium and Epiphany (WebKit), while the width of the text block grows by 10%.

- `texts.py` writes `texts.json`: the paragraph processed by `typography.py`
  (soft hyphens, no-break spaces) and a plain version without soft hyphens and
  without the last-line no-break space. It needs a `ctypography` module built
  from the current `.pyx`.
- `page.html` shows one combination after another. Spaces, rags and wide gaps
  are drawn by `content/media/js/luffy1.debug.js`, like `←←s` on the site.
  Query parameters: `text` (`raw` or `processed`), `hyphens`, `justify`,
  `pretty` (comma-separated values), `width` (start width per hyphenation mode, 770 by default, like `none:770,auto:830`), `grow` (0.1),
  `spaces=0` to hide the marks, `measure=650-900` to print line counts.
- `record.mjs` runs a browser in its own Xvfb, takes a screenshot for each
  frame and encodes a 30 fps MP4 in `out/`.

```sh
node scratch/typo-harness/record.mjs firefox firefox-plain "pretty=0"
node scratch/typo-harness/record.mjs firefox firefox-processed "text=processed&hyphens=manual&pretty=0"
node scratch/typo-harness/record.mjs chromium chromium-plain
node scratch/typo-harness/record.mjs epiphany epiphany-plain
```

Epiphany runs with `WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`, as the WebKit
sandbox does not start in the agent sandbox. Chromium has no French
hyphenation dictionary here, so `hyphens: auto` changes nothing.
