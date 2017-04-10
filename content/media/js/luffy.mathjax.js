/* Load nathjax if needed */

var luffy = luffy || {};
luffy.mathjax = function() {
    var delim = "·"; // It's "middle dot"
    var mathjax = "https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.0/MathJax.js";
    var main = document.getElementById("lf-main");

    /* Don't load if we don't find the delimiter. */
    if ((main.innerText || main.textContent || "").indexOf(delim) === -1) return;

    /* Otherwise, load. Input: TeX/AMS. Output: HTML+CSS.*/
    $script(mathjax + "?config=TeX-AMS_CHTML&delayStartupUntil=configured",
	    function() {
		  /* Add more configuration stuff */
		  MathJax.Hub.Config({
		      elements: ["lf-main"], // Only process part of the page.
		      showMathMenu: false,
		      tex2jax: {
			  inlineMath: [ [delim,delim] ],
			  displayMath: [ [delim + delim, delim + delim] ],
			  processEnvironments: false
		      },
		      "CommonHTML": {
			  scale: 97,
		      }
		  });
		  MathJax.Hub.Configured();
		  MathJax.Hub.Startup.onload();
	    });
};
