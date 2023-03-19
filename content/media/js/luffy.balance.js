/* Balance text.

  Mostly from https://github.com/Nick-Mazuk/balanced-text/blob/master/balance-text.js.

  Copyright (c) 2020 Nick Mazuk

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
 */

luffy.do(() => {
  if (CSS.supports("text-wrap", "balance")) return;

  const WORD_WRAPPER_CLASS = "balance-text-word";
  const SPACE_WRAPPER_CLASS = "balance-text-space";

  const elementIsEligible = (element) => {
    if (element.dataset.balanceTextParsed === "true") return true;
    if (element.childNodes.length === 1 && element.childNodes[0].nodeType === 3)
      return true; // if element only contains text
    return false;
  };

  const removeExistingLineBreaks = (element) => {
    element.innerHTML = element.innerHTML.replace(/<br>/g, "");
  };

  const getElementDimensions = (element) => {
    removeExistingLineBreaks(element);
    const styles = getComputedStyle(element);
    const height =
      element.clientHeight -
      parseFloat(styles.paddingTop) -
      parseFloat(styles.paddingBottom);
    const width =
      element.clientWidth -
      parseFloat(styles.paddingLeft) -
      parseFloat(styles.paddingRight);
    return { width: width, height: height };
  };

  const calcWordWidths = (element) => {
    const words = element.querySelectorAll(`.${WORD_WRAPPER_CLASS}`);
    const wordWidths = [];
    words.forEach((word) => {
      wordWidths.push(word.getBoundingClientRect().width);
    });
    return wordWidths;
  };

  const getWords = (element) => {
    const wordElements = element.querySelectorAll(`.${WORD_WRAPPER_CLASS}`);
    const words = [];
    wordElements.forEach((word) => {
      words.push(word.innerText);
    });
    return words;
  };

  const calcSpaceWidths = (element) => {
    const space = element.querySelector(`.${SPACE_WRAPPER_CLASS}`);
    return space.getBoundingClientRect().width;
  };

  const calcContentLength = (element) => {
    const totalWordLength = element.wordsLengths.reduce((a, b) => (a += b));
    const totalSpacesLength = (element.wordsLengths.length - 1) * element.space;
    return Math.floor(totalWordLength + totalSpacesLength);
  };

  const countLines = (element) => {
    let lines = 1;
    let currentLineLength = 0;
    if (element.width <= element.contentLength) return lines;
    for (let i = 0; i < element.wordsLengths.length; i++) {
      const currentWordLength = element.wordsLengths[i];
      if (currentLineLength + currentWordLength > element.width) {
        lines++;
        currentLineLength = 0;
      }
      currentLineLength += currentWordLength + element.space;
    }
    return lines;
  };

  const getDimensionsOfEveryElement = (elements) => {
    elements.forEach((element) => {
      const { width, height } = getElementDimensions(element.element);
      element["height"] = height;
      element["width"] = width;
    });
  };

  const wrapSpanAroundEveryWord = (element) => {
    const innerText = element.innerText;
    const splitText = innerText.split(" ");
    const joinText = `</span> <span class='${WORD_WRAPPER_CLASS}'>`;
    const newHTML = `<span class='${WORD_WRAPPER_CLASS}'>${splitText.join(
      joinText
    )}</span><span class='${SPACE_WRAPPER_CLASS}'>&nbsp;</span>`;
    element.innerHTML = newHTML;
  };

  const createElementsArray = (elements) => {
    const elementCollection = document.querySelectorAll(elements);
    const elementsArray = [];
    elementCollection.forEach((element) => {
      if (elementIsEligible(element)) elementsArray.push({ element: element });
    });
    return elementsArray;
  };

  const parseWords = (elementsArray) => {
    elementsArray.forEach(({ element }) => {
      wrapSpanAroundEveryWord(element);
      element.dataset.balanceTextParsed = "true";
    });
  };

  const getWordWidths = (elementsArray) => {
    elementsArray.forEach((element) => {
      element["wordsLengths"] = calcWordWidths(element.element);
      element["words"] = getWords(element.element);
      element["space"] = calcSpaceWidths(element.element);
      element["contentLength"] = calcContentLength(element);
      element["lines"] = countLines(element);
    });
  };

  const createOptimalLineBreaks = (elementsArray) => {
    elementsArray.forEach((element) => {
      if (element.lines === 1) {
        element.element.innerHTML = element.element.innerHTML.replace(
          /&nbsp;/g,
          ""
        );
      } else if (element.lines === 2) {
        let left = 0;
        let right = element.wordsLengths.length - 1;

        let firstLine = 0;
        let lastLine = 0;

        while (left < right) {
          if (
            element.wordsLengths[left] + firstLine <
            element.wordsLengths[right] + lastLine
          ) {
            firstLine += element.wordsLengths[left];
            left++;
          } else {
            lastLine += element.wordsLengths[right];
            right--;
          }
        }
        let newHTML = "";
        for (let i = 0; i < element.words.length; i++) {
          newHTML += " ";
          if (i === left) {
            if (firstLine > lastLine) {
              newHTML += `<br>${element.words[i]}`;
            } else {
              newHTML += `${element.words[i]}<br>`;
            }
          } else {
            newHTML += `${element.words[i]}`;
          }
        }
        element.element.innerHTML = newHTML;
      } else {
        const averageLineLength = element.contentLength / element.lines;
        let testLineLength = averageLineLength * 0.75;
        while (true) {
          let newHTML = "";
          let currentLineLength = 0;
          let totalLineBreaks = 1;
          for (let i = 0; i < element.wordsLengths.length; i++) {
            const currentWordLength = element.wordsLengths[i];
            if (currentLineLength + currentWordLength > testLineLength) {
              newHTML += "<br>";
              totalLineBreaks++;
              currentLineLength = 0;
            }
            newHTML += element.words[i] + " ";
            currentLineLength += currentWordLength + element.space;
          }
          if (
            totalLineBreaks <= element.lines ||
            testLineLength >= element.width
          ) {
            element.element.innerHTML = newHTML;
            break;
          }
          testLineLength = Math.min(testLineLength + 15, element.width);
        }
      }
    });
  };

  const balanceTextHelper = ({
    elements = ".has-text-balanced",
    elementsArray,
  }) => {
    if (!elementsArray) {
      elementsArray = createElementsArray(elements);
    }
    getDimensionsOfEveryElement(elementsArray);
    parseWords(elementsArray);
    getWordWidths(elementsArray);
    createOptimalLineBreaks(elementsArray);
  };

  const runBalancedText = (options) => {
    if (options.disableWait) {
      balanceTextHelper(options);
    } else if ("requestIdleCallback" in window) {
      requestIdleCallback(
        () => {
          balanceTextHelper(options);
        },
        { timeout: 1000 }
      );
    } else {
      requestAnimationFrame(() => {
        balanceTextHelper(options);
      });
    }
  };

  const balanceText = (options) => {
    runBalancedText(options);
    const timing = 200;
    window.addEventListener(
      "resize",
      debounce(() => {
        runBalancedText(options);
      }, timing)
    );
  };

  const debounce = (func, wait) => {
    let timeout;

    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };

      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  };

  balanceText({
    elements:
      ".lf-main h1, .lf-main h2, .lf-main h3, .lf-main h4, .lf-main figcaption",
  });
});
