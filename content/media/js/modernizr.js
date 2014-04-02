/* Modernizr 2.7.1 (Custom Build) | MIT & BSD
 * Build: http://modernizr.com/download/#-backgroundsize-rgba-textshadow-csstransforms-shiv-cssclasses-testprop-testallprops-prefixes-domprefixes-css_hyphens-cssclassprefix:mod!
 */
;



window.Modernizr = (function( window, document, undefined ) {

    var version = '2.7.1',

    Modernizr = {},

    enableClasses = true,

    docElement = document.documentElement,

    mod = 'modernizr',
    modElem = document.createElement(mod),
    mStyle = modElem.style,

    inputElem  ,


    toString = {}.toString,

    prefixes = ' -webkit- -moz- -o- -ms- '.split(' '),



    omPrefixes = 'Webkit Moz O ms',

    cssomPrefixes = omPrefixes.split(' '),

    domPrefixes = omPrefixes.toLowerCase().split(' '),


    tests = {},
    inputs = {},
    attrs = {},

    classes = [],

    slice = classes.slice,

    featureName,



    _hasOwnProperty = ({}).hasOwnProperty, hasOwnProp;

    if ( !is(_hasOwnProperty, 'undefined') && !is(_hasOwnProperty.call, 'undefined') ) {
      hasOwnProp = function (object, property) {
        return _hasOwnProperty.call(object, property);
      };
    }
    else {
      hasOwnProp = function (object, property) { 
        return ((property in object) && is(object.constructor.prototype[property], 'undefined'));
      };
    }


    if (!Function.prototype.bind) {
      Function.prototype.bind = function bind(that) {

        var target = this;

        if (typeof target != "function") {
            throw new TypeError();
        }

        var args = slice.call(arguments, 1),
            bound = function () {

            if (this instanceof bound) {

              var F = function(){};
              F.prototype = target.prototype;
              var self = new F();

              var result = target.apply(
                  self,
                  args.concat(slice.call(arguments))
              );
              if (Object(result) === result) {
                  return result;
              }
              return self;

            } else {

              return target.apply(
                  that,
                  args.concat(slice.call(arguments))
              );

            }

        };

        return bound;
      };
    }

    function setCss( str ) {
        mStyle.cssText = str;
    }

    function setCssAll( str1, str2 ) {
        return setCss(prefixes.join(str1 + ';') + ( str2 || '' ));
    }

    function is( obj, type ) {
        return typeof obj === type;
    }

    function contains( str, substr ) {
        return !!~('' + str).indexOf(substr);
    }

    function testProps( props, prefixed ) {
        for ( var i in props ) {
            var prop = props[i];
            if ( !contains(prop, "-") && mStyle[prop] !== undefined ) {
                return prefixed == 'pfx' ? prop : true;
            }
        }
        return false;
    }

    function testDOMProps( props, obj, elem ) {
        for ( var i in props ) {
            var item = obj[props[i]];
            if ( item !== undefined) {

                            if (elem === false) return props[i];

                            if (is(item, 'function')){
                                return item.bind(elem || obj);
                }

                            return item;
            }
        }
        return false;
    }

    function testPropsAll( prop, prefixed, elem ) {

        var ucProp  = prop.charAt(0).toUpperCase() + prop.slice(1),
            props   = (prop + ' ' + cssomPrefixes.join(ucProp + ' ') + ucProp).split(' ');

            if(is(prefixed, "string") || is(prefixed, "undefined")) {
          return testProps(props, prefixed);

            } else {
          props = (prop + ' ' + (domPrefixes).join(ucProp + ' ') + ucProp).split(' ');
          return testDOMProps(props, prefixed, elem);
        }
    }



    tests['rgba'] = function() {
        setCss('background-color:rgba(150,255,150,.5)');

        return contains(mStyle.backgroundColor, 'rgba');
    };

    tests['backgroundsize'] = function() {
        return testPropsAll('backgroundSize');
    };

    tests['textshadow'] = function() {
        return document.createElement('div').style.textShadow === '';
    };


    tests['csstransforms'] = function() {
        return !!testPropsAll('transform');
    };


    for ( var feature in tests ) {
        if ( hasOwnProp(tests, feature) ) {
                                    featureName  = feature.toLowerCase();
            Modernizr[featureName] = tests[feature]();

            classes.push((Modernizr[featureName] ? '' : 'no-') + featureName);
        }
    }



     Modernizr.addTest = function ( feature, test ) {
       if ( typeof feature == 'object' ) {
         for ( var key in feature ) {
           if ( hasOwnProp( feature, key ) ) {
             Modernizr.addTest( key, feature[ key ] );
           }
         }
       } else {

         feature = feature.toLowerCase();

         if ( Modernizr[feature] !== undefined ) {
                                              return Modernizr;
         }

         test = typeof test == 'function' ? test() : test;

         if (typeof enableClasses !== "undefined" && enableClasses) {
           docElement.className+=" mod-" + (test ? '' : 'no-') + feature;
         }
         Modernizr[feature] = test;

       }

       return Modernizr; 
     };


    setCss('');
    modElem = inputElem = null;

    ;(function(window, document) {
                var version = '3.7.0';

            var options = window.html5 || {};

            var reSkip = /^<|^(?:button|map|select|textarea|object|iframe|option|optgroup)$/i;

            var saveClones = /^(?:a|b|code|div|fieldset|h1|h2|h3|h4|h5|h6|i|label|li|ol|p|q|span|strong|style|table|tbody|td|th|tr|ul)$/i;

            var supportsHtml5Styles;

            var expando = '_html5shiv';

            var expanID = 0;

            var expandoData = {};

            var supportsUnknownElements;

        (function() {
          try {
            var a = document.createElement('a');
            a.innerHTML = '<xyz></xyz>';
                    supportsHtml5Styles = ('hidden' in a);

            supportsUnknownElements = a.childNodes.length == 1 || (function() {
                        (document.createElement)('a');
              var frag = document.createDocumentFragment();
              return (
                typeof frag.cloneNode == 'undefined' ||
                typeof frag.createDocumentFragment == 'undefined' ||
                typeof frag.createElement == 'undefined'
              );
            }());
          } catch(e) {
                    supportsHtml5Styles = true;
            supportsUnknownElements = true;
          }

        }());

            function addStyleSheet(ownerDocument, cssText) {
          var p = ownerDocument.createElement('p'),
          parent = ownerDocument.getElementsByTagName('head')[0] || ownerDocument.documentElement;

          p.innerHTML = 'x<style>' + cssText + '</style>';
          return parent.insertBefore(p.lastChild, parent.firstChild);
        }

            function getElements() {
          var elements = html5.elements;
          return typeof elements == 'string' ? elements.split(' ') : elements;
        }

            function getExpandoData(ownerDocument) {
          var data = expandoData[ownerDocument[expando]];
          if (!data) {
            data = {};
            expanID++;
            ownerDocument[expando] = expanID;
            expandoData[expanID] = data;
          }
          return data;
        }

            function createElement(nodeName, ownerDocument, data){
          if (!ownerDocument) {
            ownerDocument = document;
          }
          if(supportsUnknownElements){
            return ownerDocument.createElement(nodeName);
          }
          if (!data) {
            data = getExpandoData(ownerDocument);
          }
          var node;

          if (data.cache[nodeName]) {
            node = data.cache[nodeName].cloneNode();
          } else if (saveClones.test(nodeName)) {
            node = (data.cache[nodeName] = data.createElem(nodeName)).cloneNode();
          } else {
            node = data.createElem(nodeName);
          }

                                                    return node.canHaveChildren && !reSkip.test(nodeName) && !node.tagUrn ? data.frag.appendChild(node) : node;
        }

            function createDocumentFragment(ownerDocument, data){
          if (!ownerDocument) {
            ownerDocument = document;
          }
          if(supportsUnknownElements){
            return ownerDocument.createDocumentFragment();
          }
          data = data || getExpandoData(ownerDocument);
          var clone = data.frag.cloneNode(),
          i = 0,
          elems = getElements(),
          l = elems.length;
          for(;i<l;i++){
            clone.createElement(elems[i]);
          }
          return clone;
        }

            function shivMethods(ownerDocument, data) {
          if (!data.cache) {
            data.cache = {};
            data.createElem = ownerDocument.createElement;
            data.createFrag = ownerDocument.createDocumentFragment;
            data.frag = data.createFrag();
          }


          ownerDocument.createElement = function(nodeName) {
                    if (!html5.shivMethods) {
              return data.createElem(nodeName);
            }
            return createElement(nodeName, ownerDocument, data);
          };

          ownerDocument.createDocumentFragment = Function('h,f', 'return function(){' +
                                                          'var n=f.cloneNode(),c=n.createElement;' +
                                                          'h.shivMethods&&(' +
                                                                                                                getElements().join().replace(/[\w\-]+/g, function(nodeName) {
            data.createElem(nodeName);
            data.frag.createElement(nodeName);
            return 'c("' + nodeName + '")';
          }) +
            ');return n}'
                                                         )(html5, data.frag);
        }

            function shivDocument(ownerDocument) {
          if (!ownerDocument) {
            ownerDocument = document;
          }
          var data = getExpandoData(ownerDocument);

          if (html5.shivCSS && !supportsHtml5Styles && !data.hasCSS) {
            data.hasCSS = !!addStyleSheet(ownerDocument,
                                                                                'article,aside,dialog,figcaption,figure,footer,header,hgroup,main,nav,section{display:block}' +
                                                                                    'mark{background:#FF0;color:#000}' +
                                                                                    'template{display:none}'
                                         );
          }
          if (!supportsUnknownElements) {
            shivMethods(ownerDocument, data);
          }
          return ownerDocument;
        }

            var html5 = {

                'elements': options.elements || 'abbr article aside audio bdi canvas data datalist details dialog figcaption figure footer header hgroup main mark meter nav output progress section summary template time video',

                'version': version,

                'shivCSS': (options.shivCSS !== false),

                'supportsUnknownElements': supportsUnknownElements,

                'shivMethods': (options.shivMethods !== false),

                'type': 'default',

                'shivDocument': shivDocument,

                createElement: createElement,

                createDocumentFragment: createDocumentFragment
        };

            window.html5 = html5;

            shivDocument(document);

    }(this, document));

    Modernizr._version      = version;

    Modernizr._prefixes     = prefixes;
    Modernizr._domPrefixes  = domPrefixes;
    Modernizr._cssomPrefixes  = cssomPrefixes;



    Modernizr.testProp      = function(prop){
        return testProps([prop]);
    };

    Modernizr.testAllProps  = testPropsAll;

    docElement.className = docElement.className.replace(/(^|\s)no-js(\s|$)/, '$1$2') +

                                                    (enableClasses ? " mod-js mod-"+classes.join(" mod-") : '');

    return Modernizr;

})(this, this.document);
/* see http://davidnewton.ca/the-current-state-of-hyphenation-on-the-web
   http://davidnewton.ca/demos/hyphenation/test.html


There are three tests:
   1. csshyphens      - tests hyphens:auto actually adds hyphens to text
   2. softhyphens     - tests that &shy; does its job
   3. softhyphensfind - tests that in-browser Find functionality still works correctly with &shy;

These tests currently require document.body to be present

Hyphenation is language specific, sometimes.
  See for more details: http://code.google.com/p/hyphenator/source/diff?spec=svn975&r=975&format=side&path=/trunk/Hyphenator.js#sc_svn975_313

If loading Hyphenator.js via Modernizr.load, be cautious of issue 158: http://code.google.com/p/hyphenator/issues/detail?id=158

More details at https://github.com/Modernizr/Modernizr/issues/312

*/

(function() {

	if (!document.body){
		window.console && console.warn('document.body doesn\'t exist. Modernizr hyphens test needs it.');
		return;
	}

	// functional test of adding hyphens:auto
	function test_hyphens_css() {
		try {
			/* create a div container and a span within that
			 * these have to be appended to document.body, otherwise some browsers can give false negative */
			var div = document.createElement('div'),
				span = document.createElement('span'),
				divStyle = div.style,
				spanHeight = 0,
				spanWidth = 0,
				result = false,
				firstChild = document.body.firstElementChild || document.body.firstChild;

			div.appendChild(span);
			span.innerHTML = 'Bacon ipsum dolor sit amet jerky velit in culpa hamburger et. Laborum dolor proident, enim dolore duis commodo et strip steak. Salami anim et, veniam consectetur dolore qui tenderloin jowl velit sirloin. Et ad culpa, fatback cillum jowl ball tip ham hock nulla short ribs pariatur aute. Pig pancetta ham bresaola, ut boudin nostrud commodo flank esse cow tongue culpa. Pork belly bresaola enim pig, ea consectetur nisi. Fugiat officia turkey, ea cow jowl pariatur ullamco proident do laborum velit sausage. Magna biltong sint tri-tip commodo sed bacon, esse proident aliquip. Ullamco ham sint fugiat, velit in enim sed mollit nulla cow ut adipisicing nostrud consectetur. Proident dolore beef ribs, laborum nostrud meatball ea laboris rump cupidatat labore culpa. Shankle minim beef, velit sint cupidatat fugiat tenderloin pig et ball tip. Ut cow fatback salami, bacon ball tip et in shank strip steak bresaola. In ut pork belly sed mollit tri-tip magna culpa veniam, short ribs qui in andouille ham consequat. Dolore bacon t-bone, velit short ribs enim strip steak nulla. Voluptate labore ut, biltong swine irure jerky. Cupidatat excepteur aliquip salami dolore. Ball tip strip steak in pork dolor. Ad in esse biltong. Dolore tenderloin exercitation ad pork loin t-bone, dolore in chicken ball tip qui pig. Ut culpa tongue, sint ribeye dolore ex shank voluptate hamburger. Jowl et tempor, boudin pork chop labore ham hock drumstick consectetur tri-tip elit swine meatball chicken ground round. Proident shankle mollit dolore. Shoulder ut duis t-bone quis reprehenderit. Meatloaf dolore minim strip steak, laboris ea aute bacon beef ribs elit shank in veniam drumstick qui. Ex laboris meatball cow tongue pork belly. Ea ball tip reprehenderit pig, sed fatback boudin dolore flank aliquip laboris eu quis. Beef ribs duis beef, cow corned beef adipisicing commodo nisi deserunt exercitation. Cillum dolor t-bone spare ribs, ham hock est sirloin. Brisket irure meatloaf in, boudin pork belly sirloin ball tip. Sirloin sint irure nisi nostrud aliqua. Nostrud nulla aute, enim officia culpa ham hock. Aliqua reprehenderit dolore sunt nostrud sausage, ea boudin pork loin ut t-bone ham tempor. Tri-tip et pancetta drumstick laborum. Ham hock magna do nostrud in proident. Ex ground round fatback, venison non ribeye in.';

			document.body.insertBefore(div, firstChild);

			/* get size of unhyphenated text */
			divStyle.cssText = 'position:absolute;top:0;left:0;width:5em;text-align:justify;text-justification:newspaper;';
			spanHeight = span.offsetHeight;
			spanWidth = span.offsetWidth;

			/* compare size with hyphenated text */
			divStyle.cssText = 'position:absolute;top:0;left:0;width:5em;text-align:justify;'+
												 'text-justification:newspaper;'+
												 Modernizr._prefixes.join('hyphens:auto; ');

			result = (span.offsetHeight != spanHeight || span.offsetWidth != spanWidth);

			/* results and cleanup */
			document.body.removeChild(div);
			div.removeChild(span);

			return result;
		} catch(e) {
			return false;
		}
	}

	// for the softhyphens test
	function test_hyphens(delimiter, testWidth) {
		try {
			/* create a div container and a span within that
			 * these have to be appended to document.body, otherwise some browsers can give false negative */
			var div = document.createElement('div'),
				span = document.createElement('span'),
				divStyle = div.style,
				spanSize = 0,
				result = false,
				result1 = false,
				result2 = false,
				firstChild = document.body.firstElementChild || document.body.firstChild;

			divStyle.cssText = 'position:absolute;top:0;left:0;overflow:visible;width:1.25em;';
			div.appendChild(span);
			document.body.insertBefore(div, firstChild);


			/* get height of unwrapped text */
			span.innerHTML = 'mm';
			spanSize = span.offsetHeight;

			/* compare height w/ delimiter, to see if it wraps to new line */
			span.innerHTML = 'm' + delimiter + 'm';
			result1 = (span.offsetHeight > spanSize);

			/* if we're testing the width too (i.e. for soft-hyphen, not zws),
			 * this is because tested Blackberry devices will wrap the text but not display the hyphen */
			if (testWidth) {
				/* get width of wrapped, non-hyphenated text */
				span.innerHTML = 'm<br />m';
				spanSize = span.offsetWidth;

				/* compare width w/ wrapped w/ delimiter to see if hyphen is present */
				span.innerHTML = 'm' + delimiter + 'm';
				result2 = (span.offsetWidth > spanSize);
			} else {
				result2 = true;
			}

			/* results and cleanup */
			if (result1 === true && result2 === true) { result = true; }
			document.body.removeChild(div);
			div.removeChild(span);

			return result;
		} catch(e) {
			return false;
		}
	}

	// testing if in-browser Find functionality will work on hyphenated text
	function test_hyphens_find(delimiter) {
		try {
			/* create a dummy input for resetting selection location, and a div container
			 * these have to be appended to document.body, otherwise some browsers can give false negative
			 * div container gets the doubled testword, separated by the delimiter
			 * Note: giving a width to div gives false positive in iOS Safari */
			var dummy = document.createElement('input'),
				div = document.createElement('div'),
				testword = 'lebowski',
				result = false,
				textrange,
				firstChild = document.body.firstElementChild || document.body.firstChild;

			div.innerHTML = testword + delimiter + testword;

			document.body.insertBefore(div, firstChild);
			document.body.insertBefore(dummy, div);


			/* reset the selection to the dummy input element, i.e. BEFORE the div container
			 *   stackoverflow.com/questions/499126/jquery-set-cursor-position-in-text-area */
			if (dummy.setSelectionRange) {
				dummy.focus();
				dummy.setSelectionRange(0,0);
			} else if (dummy.createTextRange) {
				textrange = dummy.createTextRange();
				textrange.collapse(true);
				textrange.moveEnd('character', 0);
				textrange.moveStart('character', 0);
				textrange.select();
			}

			/* try to find the doubled testword, without the delimiter */
			if (window.find) {
				result = window.find(testword + testword);
			} else {
				try {
					textrange = window.self.document.body.createTextRange();
					result = textrange.findText(testword + testword);
				} catch(e) {
					result = false;
				}
			}

			document.body.removeChild(div);
			document.body.removeChild(dummy);

			return result;
		} catch(e) {
			return false;
		}
	}

	Modernizr.addTest("csshyphens", function() {

		if (!Modernizr.testAllProps('hyphens')) return false;

		/* Chrome lies about its hyphens support so we need a more robust test
				crbug.com/107111
		*/
		try {
			return test_hyphens_css();
		} catch(e) {
			return false;
		}
	});

	Modernizr.addTest("softhyphens", function() {
		try {
			// use numeric entity instead of &shy; in case it's XHTML
			return test_hyphens('&#173;', true) && test_hyphens('&#8203;', false);
		} catch(e) {
			return false;
		}
	});

	Modernizr.addTest("softhyphensfind", function() {
		try {
			return test_hyphens_find('&#173;') && test_hyphens_find('&#8203;');
		} catch(e) {
			return false;
		}
	});

})();
;
