/* Balance text.

  Mostly from https://codeberg.org/da/text-balancer/

  © 2021 Daniel Aleksandersen <https://www.daniel.priv.no/>
  SPDX-License-Identifier: Apache-2.0

  © 2016–2017 The New York Times Company <https://www.nytco.com/>
  SPDX-License-Identifier: Apache-2.0
 */

luffy.do(() => {
  if (CSS.supports("text-wrap", "balance")) return;

  const elementSelector =
    ".lf-main h1, .lf-main h2, .lf-main h3, .lf-main h4, .lf-main figcaption";

  function balanceText(element) {
    if (textElementIsMultipleLines(element)) {
      element.style.maxWidth = null;
      var width = element.parentElement.clientWidth;
      var bottomRange = Math.max(100, parseInt(width / 2));
      squeezeContainer(element, element.clientHeight, bottomRange, width);
    }
  }

  // Make the headline element as narrow as possible while maintaining its
  // current height (number of lines). Binary search.
  function squeezeContainer(headline, originalHeight, bottomRange, topRange) {
    var mid;
    if (bottomRange + 4 >= topRange) {
      headline.style.maxWidth = Math.ceil(topRange) + "px";
      return;
    }
    mid = (bottomRange + topRange) / 2;
    headline.style.maxWidth = mid + "px";

    if (headline.clientHeight > originalHeight) {
      // We've squeezed too far and headline has spilled onto an additional line;
      // recurse on wider range
      squeezeContainer(headline, originalHeight, mid, topRange);
    } else {
      // Headline has not wrapped to another line; keep squeezing!
      squeezeContainer(headline, originalHeight, bottomRange, mid);
    }
  }

  // Check if element text spans multiple lines
  var textElementIsMultipleLines = function (element) {
    var elementStyles = window.getComputedStyle(element);
    var elementLineHeight = parseInt(elementStyles["line-height"], 10);
    var elementHeight = parseInt(elementStyles["height"], 10);
    return elementLineHeight < elementHeight;
  };

  function initialize() {
    var candidates = document.querySelectorAll(elementSelector);

    if (window.ResizeObserver) {
      const observer = new ResizeObserver(function (entries) {
        entries.forEach(function (entry) {
          let elements = entry.target.querySelectorAll(elementSelector);
          for (let element of elements) {
            balanceText(element);
          }
        });
      });
      for (let element of candidates) {
        observer.observe(element.parentElement);
      }
    }
  }

  initialize();
});
