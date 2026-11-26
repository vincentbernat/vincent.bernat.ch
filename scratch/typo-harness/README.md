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
  `pretty` (comma-separated values), `width` (start width per hyphenation mode, 810 by default, like `none:810,auto:830`), `grow` (0.1),
  `spaces=0` to hide the marks, `measure=650-900` to print line counts,
  `layout=1` to record the position of each word instead of frames. The text
  is upright Literata without ligatures, like the SVG.
- `record.mjs` runs a browser in its own Xvfb, takes a screenshot for each
  frame and encodes a 30 fps MP4 in `out/`.

- `svg.mjs` writes `content/media/images/line-break.svg`, with the recorded
  layouts of the four animations and the player of `svg-player.js` inlined.
  The fragment of its URL selects the animation (`#firefox`, `#chrome`,
  `#webkit`, `#preprocess`): each one is a row of the SVG with a `<view>`
  showing it, so an `<img>` shows the first frame of the row. It plays on its
  own, `content/media/js/wip.js` adds the checkboxes and talks to it with
  messages. The build embeds Literata and Source Sans 3 subsets in it. Media
  must be served without CSP, like in production.

```sh
node scratch/typo-harness/record.mjs firefox firefox-plain-layout "layout=1&pretty=0"
node scratch/typo-harness/record.mjs firefox firefox-processed-layout "layout=1&text=processed&hyphens=manual&pretty=0"
node scratch/typo-harness/record.mjs chromium chromium-plain-layout "layout=1"
node scratch/typo-harness/record.mjs epiphany epiphany-plain-layout "layout=1"
node scratch/typo-harness/svg.mjs
```

Videos:

```sh
node scratch/typo-harness/record.mjs firefox firefox-plain "pretty=0"
node scratch/typo-harness/record.mjs firefox firefox-processed "text=processed&hyphens=manual&pretty=0"
node scratch/typo-harness/record.mjs chromium chromium-plain
node scratch/typo-harness/record.mjs epiphany epiphany-plain
```

Epiphany runs with `WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`, as the WebKit
sandbox does not start in the agent sandbox. Chromium gets its French
hyphenation dictionary from `chromium-profile/hyphen-data`.
