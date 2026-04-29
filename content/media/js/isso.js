/******/ (function() { // webpackBootstrap
/******/ 	var __webpack_modules__ = ({

/***/ "./isso/js/app/api.js":
/*!****************************!*\
  !*** ./isso/js/app/api.js ***!
  \****************************/
/***/ (function(module, __unused_webpack_exports, __webpack_require__) {

var Q = __webpack_require__(/*! app/lib/promise */ "./isso/js/app/lib/promise.js");
var globals = __webpack_require__(/*! app/globals */ "./isso/js/app/globals.js");

"use strict";

var salt = "Eech7co8Ohloopo9Ol6baimi",
    location = function() { return window.location.pathname };

var script, endpoint,
    js = document.getElementsByTagName("script");

// prefer `data-isso="//host/api/endpoint"` if provided
for (var i = 0; i < js.length; i++) {
    if (js[i].hasAttribute("data-isso")) {
        endpoint = js[i].getAttribute("data-isso");
        break;
    }
}

// if no async-script is embedded, use the last script tag of `js`
if (! endpoint) {
    for (i = 0; i < js.length; i++) {
        if (js[i].getAttribute("async") || js[i].getAttribute("defer")) {
            throw "Isso's automatic configuration detection failed, please " +
                  "refer to https://github.com/isso-comments/isso#client-configuration " +
                  "and add a custom `data-isso` attribute.";
        }
    }

    script = js[js.length - 1];
    endpoint = script.src.substring(0, script.src.length - "/js/embed.min.js".length);
}

//  strip trailing slash
if (endpoint[endpoint.length - 1] === "/") {
    endpoint = endpoint.substring(0, endpoint.length - 1);
}

var curl = function(method, url, data, resolve, reject) {

    var xhr = new XMLHttpRequest();

    function onload() {

        var date = xhr.getResponseHeader("Date");
        if (date !== null) {
            globals.offset.update(new Date(date));
        }

        var cookie = xhr.getResponseHeader("X-Set-Cookie");
        if (cookie && cookie.match(/^isso-/)) {
            document.cookie = cookie;
        }

        if (xhr.status >= 500) {
            if (reject) {
                reject(xhr.body);
            }
        } else {
            resolve({status: xhr.status, body: xhr.responseText});
        }
    }

    try {
        xhr.open(method, url, true);
        xhr.withCredentials = true;
        xhr.setRequestHeader("Content-Type", "application/json");

        xhr.onreadystatechange = function () {
            if (xhr.readyState === 4) {
                onload();
            }
        };
    } catch (exception) {
        (reject || console.log)(exception.message);
    }

    xhr.send(data);
};

var qs = function(params) {
    var rv = "";
    for (var key in params) {
        if (params.hasOwnProperty(key) &&
            params[key] !== null && typeof(params[key]) !== "undefined") {
            rv += key + "=" + encodeURIComponent(params[key]) + "&";
        }
    }

    return rv.substring(0, rv.length - 1);  // chop off trailing "&"
};

var create = function(tid, data) {
    var deferred = Q.defer();
    curl("POST", endpoint + "/new?" + qs({uri: tid || location()}), JSON.stringify(data),
        function (rv) {
            if (rv.status === 201 || rv.status === 202) {
                deferred.resolve(JSON.parse(rv.body));
            } else {
                deferred.reject(rv.body);
            }
        });
    return deferred.promise;
};

var modify = function(id, data) {
    var deferred = Q.defer();
    curl("PUT", endpoint + "/id/" + id, JSON.stringify(data), function (rv) {
        if (rv.status === 403) {
            deferred.reject("Not authorized to modify this comment!");
        } else if (rv.status === 200) {
            deferred.resolve(JSON.parse(rv.body));
        } else {
            deferred.reject(rv.body);
        }
    });
    return deferred.promise;
};

var remove = function(id) {
    var deferred = Q.defer();
    curl("DELETE", endpoint + "/id/" + id, null, function(rv) {
        if (rv.status === 403) {
            deferred.reject("Not authorized to remove this comment!");
        } else if (rv.status === 200) {
            deferred.resolve(JSON.parse(rv.body) === null);
        } else {
            deferred.reject(rv.body);
        }
    });
    return deferred.promise;
};

var view = function(id, plain) {
    var deferred = Q.defer();
    curl("GET", endpoint + "/id/" + id + "?" + qs({plain: plain}), null,
        function(rv) { deferred.resolve(JSON.parse(rv.body)); });
    return deferred.promise;
};

var fetch = function({ tid, limit = "inf", nested_limit = "inf", parent = null, sort = "", offset = 0 }) {
    var query_dict = { uri: tid || location(), sort, parent, offset };

    if (limit !== "inf") {
        query_dict['limit'] = limit;
    }
    if (nested_limit !== "inf") {
        query_dict['nested_limit'] = nested_limit;
    }

    var deferred = Q.defer();
    curl("GET", endpoint + "/?" +
        qs(query_dict), null, function(rv) {
            if (rv.status === 200) {
                deferred.resolve(JSON.parse(rv.body));
            } else {
                deferred.reject(rv.body);
            }
        });
    return deferred.promise;
};

var config = function() {
    var deferred = Q.defer();
    curl("GET", endpoint + "/config", null, function(rv) {
        if (rv.status === 200) {
            deferred.resolve(JSON.parse(rv.body));
        } else {
            deferred.reject(rv.body);
        }
    });
    return deferred.promise;
};

var count = function(urls) {
    var deferred = Q.defer();
    curl("POST", endpoint + "/count", JSON.stringify(urls), function(rv) {
        if (rv.status === 200) {
            deferred.resolve(JSON.parse(rv.body));
        } else {
            deferred.reject(rv.body);
        }
    });
    return deferred.promise;
};

var feed = function(tid) {
    return endpoint + "/feed?" + qs({uri: tid || location()});
};

var preview = function(text) {
    var deferred = Q.defer();
    curl("POST", endpoint + "/preview", JSON.stringify({text: text}),
         function(rv) {
             if (rv.status === 200) {
                 deferred.resolve(JSON.parse(rv.body).text);
             } else {
                 deferred.reject(rv.body);
             }
         });
    return deferred.promise;
};

module.exports = {
    endpoint: endpoint,
    salt: salt,
    create: create,
    modify: modify,
    remove: remove,
    view: view,
    fetch: fetch,
    count: count,
    feed: feed,
    preview: preview,
    config: config,
};


/***/ }),

/***/ "./isso/js/app/config.js":
/*!*******************************!*\
  !*** ./isso/js/app/config.js ***!
  \*******************************/
/***/ (function(module, __unused_webpack_exports, __webpack_require__) {

var default_config = __webpack_require__(/*! app/default_config */ "./isso/js/app/default_config.js");
var utils = __webpack_require__(/*! app/utils */ "./isso/js/app/utils.js");

"use strict";

// Preserve default values to filter out when comparing
// with values fetched from server
var config = {};
for (var key in default_config) {
    config[key] = default_config[key];
}

var js = document.getElementsByTagName("script");

for (var i = 0; i < js.length; i++) {
    for (var j = 0; j < js[i].attributes.length; j++) {
        var attr = js[i].attributes[j];
        if (/^data-isso-/.test(attr.name)) {

            // Normalize underscores to dashes so that language-specific
            // strings can be caught better later on, e.g.
            // data-isso-postbox-text-text-PT_BR becomes postbox-text-text-pt-br.
            // Also note that attr.name only gives lowercase strings as per HTML
            // spec, e.g. data-isso-FOO-Bar becomes foo-bar, but since the test
            // environment's jest-environment-jsdom seemingly does not follow
            // that convention, convert to lowercase here anyway.
            const attrName = attr.name.substring(10)
                       .replace(/_/g, '-')
                       .toLowerCase()

            // Replace escaped newline characters in the attribute value with actual newline characters
            const attrValue = attr.value.replace(/\\n/g, '\n');

            try {
                config[attrName] = JSON.parse(attrValue);
            } catch (ex) {
                config[attrName] = attrValue;
            }
        }
    }
}

// split avatar-fg on whitespace
config["avatar-fg"] = config["avatar-fg"].split(" ");

// create an array of normalized language codes from:
//   - config["lang"], if it is nonempty
//   - the first of navigator.languages, navigator.language, and
//     navigator.userLanguage that exists and has a nonempty value
//   - config["default-lang"]
//   - "en" as an ultimate fallback
// i18n.js will use the first code in this array for which we have
// a translation.
var languages = [];
var found_navlang = false;
if (config["lang"]) {
    languages.push(utils.normalize_bcp47(config["lang"]));
}
if (navigator.languages) {
    for (i = 0; i < navigator.languages.length; i++) {
        if (navigator.languages[i]) {
            found_navlang = true;
            languages.push(utils.normalize_bcp47(navigator.languages[i]));
        }
    }
}
if (!found_navlang && navigator.language) {
    found_navlang = true;
    languages.push(utils.normalize_bcp47(navigator.language));
}
if (!found_navlang && navigator.userLanguage) {
    found_navlang = true;
    languages.push(utils.normalize_bcp47(navigator.userLanguage));
}
if (config["default-lang"]) {
    languages.push(utils.normalize_bcp47(config["default-lang"]));
}
languages.push("en");

config["langs"] = languages;
// code outside this file should look only at langs
delete config["lang"];
delete config["default-lang"];

// Convert page-author-hash into a array by splitting at whitespace and/or commas
config["page-author-hashes"] = config["page-author-hashes"].split(/[\s,]+/);

module.exports = config;


/***/ }),

/***/ "./isso/js/app/default_config.js":
/*!***************************************!*\
  !*** ./isso/js/app/default_config.js ***!
  \***************************************/
/***/ (function(module) {

"use strict";


var default_config = {
    "css": true,
    "css-url": null,
    "lang": null,
    "default-lang": "en",
    "reply-to-self": false,
    "require-email": false,
    "require-author": false,
    "reply-notifications": true,
    "reply-notifications-default-enabled": false,
    "max-comments-top": "inf",
    "max-comments-nested": 10,
    "reveal-on-click": 5,
    "sorting": "oldest",
    "gravatar": false,
    "avatar": true,
    "avatar-bg": "#f0f0f0",
    "avatar-fg": ["#9abf88", "#5698c4", "#e279a3", "#9163b6",
                  "#be5168", "#f19670", "#e4bf80", "#447c69"].join(" "),
    "feed": false,
    "page-author-hashes": "",
};
Object.freeze(default_config);

module.exports = default_config;


/***/ }),

/***/ "./isso/js/app/dom.js":
/*!****************************!*\
  !*** ./isso/js/app/dom.js ***!
  \****************************/
/***/ (function(module) {

"use strict";


function Element(node) {
    this.obj = node;

    this.replace = function (el) {
        var element = DOM.htmlify(el);
        node.parentNode.replaceChild(element.obj, node);
        return element;
    };

    this.prepend = function (el) {
        var element = DOM.htmlify(el);
        node.insertBefore(element.obj, node.firstChild);
        return element;
    };

    this.append = function (el) {
        var element = DOM.htmlify(el);
        node.appendChild(element.obj);
        return element;
    };

    this.insertAfter = function(el) {
        var element = DOM.htmlify(el);
        node.parentNode.insertBefore(element.obj, node.nextSibling);
        return element;
    };

    /**
     * Shortcut for `Element.addEventListener`, prevents default event
     * by default, set :param prevents: to `false` to change that behavior.
     */
    this.on = function(type, listener, prevent) {
        node.addEventListener(type, function(event) {
            listener(event);
            if (prevent === undefined || prevent) {
                event.preventDefault();
            }
        });
    };

    /**
     * Toggle between two internal states on event :param type: e.g. to
     * cycle form visibility. Callback :param a: is called on first event,
     * :param b: next time.
     *
     * You can skip to the next state without executing the callback with
     * `toggler.next()`. You can prevent a cycle when you call `toggler.wait()`
     * during an event.
     */
    this.toggle = function(type, a, b) {

        var toggler = new Toggle(a, b);
        this.on(type, function() {
            toggler.next();
        });
    };

    this.detach = function() {
        // Detach an element from the DOM and return it.
        node.parentNode.removeChild(this.obj);
        return this;
    };

    this.remove = function() {
        // IE quirks
        node.parentNode.removeChild(this.obj);
    };

    this.show = function() {
        node.style.display = "block";
    };

    this.hide = function() {
        node.style.display = "none";
    };

    this.setText = function(text) {
        node.textContent = text;
    };

    this.setHtml = function(html) {
        node.innerHTML = html;
    };

    this.blur = function() { node.blur() };
    this.focus = function() { node.focus() };
    this.scrollIntoView = function(args) { node.scrollIntoView(args) };

    this.checked = function() { return node.checked; };

    this.setAttribute = function(key, value) { node.setAttribute(key, value) };
    this.getAttribute = function(key) { return node.getAttribute(key) };

    this.classList = node.classList;

    Object.defineProperties(this, {
        "textContent": {
            get: function() { return node.textContent; },
            set: function(textContent) { node.textContent = textContent; }
        },
        "innerHTML": {
            get: function() { return node.innerHTML; },
            set: function(innerHTML) { node.innerHTML = innerHTML; }
        },
        "value": {
            get: function() { return node.value; },
            set: function(value) { node.value = value; }
        },
        "placeholder": {
            get: function() { return node.placeholder; },
            set: function(placeholder) { node.placeholder = placeholder; }
        }
    });
}

var Toggle = function(a, b) {
    this.state = false;

    this.next = function() {
        if (! this.state) {
            this.state = true;
            a(this);
        } else {
            this.state = false;
            b(this);
        }
    };

    this.wait = function() {
        this.state = ! this.state;
    };
};

var DOM = function(query, root, single) {
    /*
    jQuery-like CSS selector which returns on :param query: either a
    single node (unless single=false), a node list or null.

    :param root: only queries within the given element.
     */

    if (typeof single === "undefined") {
        single = true;
    }

    if (! root) {
        root = window.document;
    }

    if (root instanceof Element) {
        root = root.obj;
    }
    var elements = [].slice.call(root.querySelectorAll(query), 0);

    if (elements.length === 0) {
        return null;
    }

    if (elements.length === 1 && single) {
        return new Element(elements[0]);
    }

    // convert NodeList to Array
    elements = [].slice.call(elements, 0);

    return elements.map(function(el) {
        return new Element(el);
    });
};

DOM.htmlify = function(el) {
    /*
    Convert :param html: into an Element (if not already).
    */

    if (el instanceof Element) {
        return el;
    }

    if (el instanceof window.Element) {
        return new Element(el);
    }

    var wrapper = DOM.new("div");
    wrapper.innerHTML = el;
    return new Element(wrapper.firstChild);
};

DOM.new = function(tag, content) {
    /*
    A helper to build HTML with pure JS. You can pass class names and
    default content as well:

        var par = DOM.new("p"),
            div = DOM.new("p.some.classes"),
            div = DOM.new("textarea.foo", "...")
     */

    var el = document.createElement(tag.split(".")[0]);
    tag.split(".").slice(1).forEach(function(val) { el.classList.add(val); });

    if (["A", "LINK"].indexOf(el.nodeName) > -1) {
        el.href = "#";
    }

    if (!content && content !== 0) {
        content = "";
    }
    if (["TEXTAREA", "INPUT"].indexOf(el.nodeName) > -1) {
        el.value = content;
    } else {
        el.textContent = content;
    }
    return el;
};

DOM.each = function(tag, func) {
    // XXX really needed? Maybe better as NodeList method
    Array.prototype.forEach.call(document.getElementsByTagName(tag), func);
};

module.exports = DOM;


/***/ }),

/***/ "./isso/js/app/globals.js":
/*!********************************!*\
  !*** ./isso/js/app/globals.js ***!
  \********************************/
/***/ (function(module) {

"use strict";


var Offset = function() {
    this.values = [];
};

Offset.prototype.update = function(remoteTime) {
    this.values.push((new Date()).getTime() - remoteTime.getTime());
};

Offset.prototype.localTime = function() {
    return new Date((new Date()).getTime() - this.values.reduce(
        function(a, b) { return a + b; }, 0) / this.values.length);
};

var offset = new Offset();

module.exports = {
    offset: offset,
}


/***/ }),

/***/ "./isso/js/app/i18n.js":
/*!*****************************!*\
  !*** ./isso/js/app/i18n.js ***!
  \*****************************/
/***/ (function(module, __unused_webpack_exports, __webpack_require__) {

"use strict";


var config = __webpack_require__(/*! app/config */ "./isso/js/app/config.js");

var catalogue = {
    en: __webpack_require__(/*! app/i18n/en */ "./isso/js/app/i18n/en.js"),
    fr: __webpack_require__(/*! app/i18n/fr */ "./isso/js/app/i18n/fr.js"),
};

var pluralforms = function(lang) {
    // we currently only need to look at the primary language
    // subtag.
    switch (lang.split("-", 1)[0]) {
    case "en":
        return function(msgs, n) {
            return msgs[n === 1 ? 0 : 1];
        };
    case "fr":
        return function(msgs, n) {
            return msgs[n > 1 ? 1 : 0];
        };
    default:
        return null;
    }
};

// for each entry in config.langs, see whether we have a catalogue
// entry and a pluralforms entry for it.  if we don't, try chopping
// off everything but the primary language subtag, before moving
// on to the next one.
var lang, plural, translations;
for (var i = 0; i < config.langs.length; i++) {
    lang = config.langs[i];
    plural = pluralforms(lang);
    translations = catalogue[lang];
    if (plural && translations)
        break;
    if (/-/.test(lang)) {
        lang = lang.split("-", 1)[0];
        plural = pluralforms(lang);
        translations = catalogue[lang];
        if (plural && translations)
            break;
    }
}

// absolute backstop; if we get here there's a bug in config.js
if (!plural || !translations) {
    lang = "en";
    plural = pluralforms(lang);
    translations = catalogue[lang];
}

var translate = function(msgid) {
    // Need to convert the language string to lowercase because data-isso-*
    // attributes are automatically cast to lowercase as per HTML spec
    // https://stackoverflow.com/questions/36176474/camel-case-in-html-tag-attributes-and-jquery-doesnt-work-why
    return config[msgid + '-text-' + lang.toLowerCase()] ||
      translations[msgid] ||
      catalogue.en[msgid] ||
      "[?" + msgid + "]";
};

var pluralize = function(msgid, n) {
    var msg;

    msg = translate(msgid);
    if (msg.indexOf("\n") > -1) {
        msg = plural(msg.split("\n"), (+ n));
    }

    return msg ? msg.replace("{{ n }}", (+ n)) : msg;
};

var ago = function(localTime, date) {

    var secs = ((localTime.getTime() - date.getTime()) / 1000);

    if (isNaN(secs) || secs < 0 ) {
        secs = 0;
    }

    var mins = Math.floor(secs / 60), hours = Math.floor(mins / 60),
        days = Math.floor(hours / 24);

    return secs  <=  45 && translate("date-now")  ||
           secs  <=  90 && pluralize("date-minute", 1) ||
           mins  <=  45 && pluralize("date-minute", mins) ||
           mins  <=  90 && pluralize("date-hour", 1) ||
           hours <=  22 && pluralize("date-hour", hours) ||
           hours <=  36 && pluralize("date-day", 1) ||
           days  <=   5 && pluralize("date-day", days) ||
           days  <=   8 && pluralize("date-week", 1) ||
           days  <=  21 && pluralize("date-week", Math.floor(days / 7)) ||
           days  <=  45 && pluralize("date-month", 1) ||
           days  <= 345 && pluralize("date-month", Math.floor(days / 30)) ||
           days  <= 547 && pluralize("date-year", 1) ||
                           pluralize("date-year", Math.floor(days / 365.25));
};

module.exports = {
    ago: ago,
    lang: lang,
    translate: translate,
    pluralize: pluralize,
};


/***/ }),

/***/ "./isso/js/app/i18n/en.js":
/*!********************************!*\
  !*** ./isso/js/app/i18n/en.js ***!
  \********************************/
/***/ (function(module) {

module.exports = {
    "postbox-text": "Type comment here (at least 3 chars)",
    "postbox-author": "Name (optional)",
    "postbox-author-placeholder": "John Doe",
    "postbox-email": "Email (optional)",
    "postbox-email-placeholder": "johndoe@example.com",
    "postbox-website": "Website (optional)",
    "postbox-website-placeholder": "https://example.com",
    "postbox-preview": "Preview",
    "postbox-edit": "Edit",
    "postbox-submit": "Submit",
    "postbox-notification": "Subscribe to email notification of replies",

    "num-comments": "One comment\n{{ n }} comments",
    "no-comments": "No comments yet",
    "atom-feed": "Atom feed",

    "comment-reply": "Reply",
    "comment-edit": "Edit",
    "comment-save": "Save",
    "comment-delete": "Delete",
    "comment-confirm": "Confirm",
    "comment-close": "Close",
    "comment-cancel": "Cancel",
    "comment-deleted": "Comment deleted.",
    "comment-queued": "Comment in queue for moderation.",
    "comment-anonymous": "Anonymous",
    "comment-hidden": "{{ n }} more",
    "comment-page-author-suffix": "Author",

    "date-now": "right now",
    "date-minute": "a minute ago\n{{ n }} minutes ago",
    "date-hour": "an hour ago\n{{ n }} hours ago",
    "date-day": "Yesterday\n{{ n }} days ago",
    "date-week": "last week\n{{ n }} weeks ago",
    "date-month": "last month\n{{ n }} months ago",
    "date-year": "last year\n{{ n }} years ago"
};


/***/ }),

/***/ "./isso/js/app/i18n/fr.js":
/*!********************************!*\
  !*** ./isso/js/app/i18n/fr.js ***!
  \********************************/
/***/ (function(module) {

module.exports= {
    "postbox-text": "Insérez votre commentaire ici (au moins 3 lettres)",
    "postbox-author": "Nom (optionnel)",
    "postbox-email": "Courriel (optionnel)",
    "postbox-website": "Site web (optionnel)",
    "postbox-preview": "Aperçu",
    "postbox-edit": "Éditer",
    "postbox-submit": "Soumettre",
    "postbox-notification": "S’abonner aux notifications de réponses",
    "num-comments": "{{ n }} commentaire\n{{ n }} commentaires",
    "no-comments": "Aucun commentaire pour l’instant",
    "atom-feed": "Flux Atom",
    "comment-reply": "Répondre",
    "comment-edit": "Éditer",
    "comment-save": "Enregistrer",
    "comment-delete": "Supprimer",
    "comment-confirm": "Confirmer",
    "comment-close": "Fermer",
    "comment-cancel": "Annuler",
    "comment-deleted": "Commentaire supprimé.",
    "comment-queued": "Commentaire en attente de modération.",
    "comment-anonymous": "Anonyme",
    "comment-hidden": "1 supplémentaire\n{{ n }} supplémentaires",
    "date-now": "À l’instant",
    "date-minute": "Il y a une minute\nIl y a {{ n }} minutes",
    "date-hour": "Il y a une heure\nIl y a {{ n }} heures ",
    "date-day": "Hier\nIl y a {{ n }} jours",
    "date-week": "Il y a une semaine\nIl y a {{ n }} semaines",
    "date-month": "Il y a un mois\nIl y a {{ n }} mois",
    "date-year": "Il y a un an\nIl y a {{ n }} ans"
};


/***/ }),

/***/ "./isso/js/app/isso.js":
/*!*****************************!*\
  !*** ./isso/js/app/isso.js ***!
  \*****************************/
/***/ (function(module, __unused_webpack_exports, __webpack_require__) {

/* Isso – Ich schrei sonst!
*/
var $ = __webpack_require__(/*! app/dom */ "./isso/js/app/dom.js");
var utils = __webpack_require__(/*! app/utils */ "./isso/js/app/utils.js");
var config = __webpack_require__(/*! app/config */ "./isso/js/app/config.js");
var api = __webpack_require__(/*! app/api */ "./isso/js/app/api.js");
var template = __webpack_require__(/*! app/template */ "./isso/js/app/template.js");
var i18n = __webpack_require__(/*! app/i18n */ "./isso/js/app/i18n.js");
var identicons = __webpack_require__(/*! app/lib/identicons */ "./isso/js/app/lib/identicons.js");
var globals = __webpack_require__(/*! app/globals */ "./isso/js/app/globals.js");

"use strict";

var Postbox = function(parent) {

    var localStorage = utils.localStorageImpl,
        el = $.htmlify(template.render("postbox", {
        "author":  JSON.parse(localStorage.getItem("isso-author")),
        "email":   JSON.parse(localStorage.getItem("isso-email")),
        "website": JSON.parse(localStorage.getItem("isso-website")),
        "preview": ''
    }));

    // callback on success (e.g. to toggle the reply button)
    el.onsuccess = function() {};

    el.validate = function() {
        if ($(".isso-textarea", this).value.length < 3) {
            $(".isso-textarea", this).focus();
            return false;
        }
        if (config["require-email"] &&
            $("[name='email']", this).value.length <= 0)
        {
          $("[name='email']", this).focus();
          return false;
        }
        if (config["require-author"] &&
            $("[name='author']", this).value.length <= 0)
        {
          $("[name='author']", this).focus();
          return false;
        }
        return true;
    };

    // only display notification checkbox if email is filled in
    var email_edit = function() {
        if (config["reply-notifications"] && $("[name='email']", el).value.length > 0) {
            $(".isso-notification-section", el).show();
        } else {
            $(".isso-notification-section", el).hide();
        }
    };
    $("[name='email']", el).on("input", email_edit);
    email_edit();

    // email is not optional if this config parameter is set
    if (config["require-email"]) {
        $("[for='isso-postbox-email']", el).textContent =
            $("[for='isso-postbox-email']", el).textContent.replace(/ \(.*\)/, "");
    }

    // author is not optional if this config parameter is set
    if (config["require-author"]) {
      $("[for='isso-postbox-author']", el).textContent =
        $("[for='isso-postbox-author']", el).textContent.replace(/ \(.*\)/, "");
    }

    // preview function
    $("[name='preview']", el).on("click", function() {
        api.preview($(".isso-textarea", el).value).then(
            function(html) {
                $(".isso-preview .isso-text", el).innerHTML = html;
                el.classList.add('isso-preview-mode');
            });
    });

    // edit function
    var edit = function() {
        $(".isso-preview .isso-text", el).innerHTML = '';
        el.classList.remove('isso-preview-mode');
    };
    $("[name='edit']", el).on("click", function() {
      edit();
      $(".isso-textarea", el).focus();
    });
    $(".isso-preview", el).on("click", function() {
      edit();
      $(".isso-textarea", el).focus();
    });

    // submit form, initialize optional fields with `null` and reset form.
    // If replied to a comment, remove form completely.
    $("[type=submit]", el).on("click", function(event) {
        edit();
        if (! el.validate()) {
            return;
        }

        const submitButton = event.target;
        submitButton.disabled = true; // Disable the submit button to prevent double posting

        var author = $("[name=author]", el).value || null,
            email = $("[name=email]", el).value || null,
            website = $("[name=website]", el).value || null;

        try {
            localStorage.setItem("isso-author", JSON.stringify(author));
            localStorage.setItem("isso-email", JSON.stringify(email));
            localStorage.setItem("isso-website", JSON.stringify(website));

            api.create($("#isso-thread").getAttribute("data-isso-id"), {
                author: author, email: email, website: website,
                text: $(".isso-textarea", el).value,
                parent: parent || null,
                title: $("#isso-thread").getAttribute("data-title") || null,
                notification: $("[name=notification]", el).checked() ? 1 : 0,
            }).then(
                function(comment) {
                    $(".isso-textarea", el).value = "";
                    insert({ comment, scrollIntoView: true, offset: 0 });

                    if (parent !== null) {
                        el.onsuccess();
                    }

                    submitButton.disabled = false;
                },
                function(err) {
                    console.error(err);
                    submitButton.disabled = false;
                }
            );
        } catch (err) {
            console.error(err);
            submitButton.disabled = false;
        }
    });

    return el;
};

var insert_loader = function(comment, offset) {
    var entrypoint;
    if (comment.id === null) {
        entrypoint = $("#isso-root");
        comment.name = 'null';
    } else {
        entrypoint = $("#isso-" + comment.id + " > .isso-follow-up");
        comment.name = comment.id;
    }
    var el = $.htmlify(template.render("comment-loader", {"comment": comment}));

    entrypoint.append(el);

    $("a.isso-load-hidden", el).on("click", function() {
        el.remove();

        api.fetch({
            tid: $("#isso-thread").getAttribute("data-isso-id"),
            limit: config["reveal-on-click"],
            nested_limit: config["max-comments-nested"],
            parent: comment.id,
            sort: config["sorting"],
            offset: offset
        }).then(
            function(rv) {
                if (rv.total_replies === 0) {
                    return;
                }

                rv.replies.forEach(function(commentObject) {
                    insert({ comment: commentObject, scrollIntoView: false, offset: 0 });

                });

                if(rv.hidden_replies > 0) {
                    insert_loader(rv, offset + rv.replies.length);
                }
            },
            function(err) {
                console.log(err);
            }
        );
    });
};

var insert = function({ comment, scrollIntoView, offset }) {
    var el = $.htmlify(template.render("comment", {"comment": comment}));

    // update datetime every 60 seconds
    var refresh = function() {
        $(".isso-permalink > time", el).textContent = i18n.ago(
            globals.offset.localTime(), new Date(parseInt(comment.created, 10) * 1000));
        setTimeout(refresh, 60*1000);
    };

    // run once to activate
    refresh();

    if (config["avatar"]) {
        $(".isso-avatar > svg", el).replace(identicons.generate(comment.hash, 4, 48, config));
    }

    var entrypoint;
    if (comment.parent === null) {
        entrypoint = $("#isso-root");
    } else {
        entrypoint = $("#isso-" + comment.parent + " > .isso-follow-up");
    }

    entrypoint.append(el);

    if (scrollIntoView) {
        el.scrollIntoView();
    }

    var footer = $("#isso-" + comment.id + " > .isso-text-wrapper > .isso-comment-footer"),
        header = $("#isso-" + comment.id + " > .isso-text-wrapper > .isso-comment-header"),
        text   = $("#isso-" + comment.id + " > .isso-text-wrapper > .isso-text");

    var form = null;  // XXX: probably a good place for a closure
    $("a.isso-reply", footer).toggle("click",
        function(toggler) {
            form = footer.insertAfter(new Postbox(comment.parent === null ? comment.id : comment.parent));
            form.onsuccess = function() { toggler.next(); };
            $(".isso-textarea", form).focus();
            $("a.isso-reply", footer).textContent = i18n.translate("comment-close");
        },
        function() {
            form.remove();
            $("a.isso-reply", footer).textContent = i18n.translate("comment-reply");
        }
    );

    $("a.isso-edit", footer).toggle("click",
        function(toggler) {
            var edit = $("a.isso-edit", footer);
            var avatar = config["avatar"] || config["gravatar"] ? $(".isso-avatar", el, false)[0] : null;

            edit.textContent = i18n.translate("comment-save");
            edit.insertAfter($.new("a.isso-cancel", i18n.translate("comment-cancel"))).on("click", function() {
                toggler.canceled = true;
                toggler.next();
            });

            toggler.canceled = false;
            api.view(comment.id, 1).then(function(rv) {
                var textarea = $.new("textarea.isso-textarea");
                textarea.setAttribute("rows", 5);
                textarea.setAttribute("minlength", 3);
                textarea.setAttribute("maxlength", 65535);

                textarea.value = rv.text;
                textarea.focus();

                text.classList.remove("isso-text");
                text.classList.add("isso-textarea-wrapper");

                text.textContent = "";
                text.append(textarea);
            });

            if (avatar !== null) {
                avatar.hide();
            }
        },
        function(toggler) {
            var textarea = $(".isso-textarea", text);
            var avatar = config["avatar"] || config["gravatar"] ? $(".isso-avatar", el, false)[0] : null;

            if (! toggler.canceled && textarea !== null) {
                if (textarea.value.length < 3) {
                    textarea.focus();
                    toggler.wait();
                    return;
                } else {
                    api.modify(comment.id, {"text": textarea.value}).then(function(rv) {
                        text.innerHTML = rv.text;
                        comment.text = rv.text;
                    });
                }
            } else {
                text.innerHTML = comment.text;
            }

            text.classList.remove("isso-textarea-wrapper");
            text.classList.add("isso-text");

            if (avatar !== null) {
                avatar.show();
            }

            $("a.isso-cancel", footer).remove();
            $("a.isso-edit", footer).textContent = i18n.translate("comment-edit");
        }
    );

    $("a.isso-delete", footer).toggle("click",
        function(toggler) {
            var del = $("a.isso-delete", footer);
            var state = ! toggler.state;

            del.textContent = i18n.translate("comment-confirm");
            del.on("mouseout", function() {
                del.textContent = i18n.translate("comment-delete");
                toggler.state = state;
                del.onmouseout = null;
            });
        },
        function() {
            var del = $("a.isso-delete", footer);
            api.remove(comment.id).then(function(rv) {
                if (rv) {
                    el.remove();
                } else {
                    $("span.isso-note", header).textContent = i18n.translate("comment-deleted");
                    text.innerHTML = "<p>&nbsp;</p>";
                    $("a.isso-edit", footer).remove();
                    $("a.isso-delete", footer).remove();
                }
                del.textContent = i18n.translate("comment-delete");
            });
        }
    );

    // remove edit and delete buttons when cookie is gone
    var clear = function(button) {
        if (! utils.cookie("isso-" + comment.id)) {
            if ($(button, footer) !== null) {
                $(button, footer).remove();
            }
        } else {
            setTimeout(function() { clear(button); }, 15*1000);
        }
    };

    clear("a.isso-edit");
    clear("a.isso-delete");

    // show direct reply to own comment when cookie is max aged
    var show = function(el) {
        if (utils.cookie("isso-" + comment.id)) {
            setTimeout(function() { show(el); }, 15*1000);
        } else {
            footer.append(el);
        }
    };

    if (! config["reply-to-self"] && utils.cookie("isso-" + comment.id)) {
        show($("a.isso-reply", footer).detach());
    }

    if (comment.hasOwnProperty('replies')) {
        comment.replies.forEach(function (replyObject) {
            insert({ comment: replyObject, scrollIntoView: false, offset: offset + 1 });
        });
        if (comment.hidden_replies > 0) {
            insert_loader(comment, offset + comment.replies.length);
        }
    }

};

module.exports = {
    insert: insert,
    insert_loader: insert_loader,
    Postbox: Postbox,
};


/***/ }),

/***/ "./isso/js/app/lib/identicons.js":
/*!***************************************!*\
  !*** ./isso/js/app/lib/identicons.js ***!
  \***************************************/
/***/ (function(module, __unused_webpack_exports, __webpack_require__) {

/*
  Copyright (C) 2013 Gregory Schier <gschier1990@gmail.com>
  Copyright (C) 2013 Martin Zimmermann <info@posativ.org>

  Inspired by http://codepen.io/gschier/pen/GLvAy
*/
var Q = __webpack_require__(/*! app/lib/promise */ "./isso/js/app/lib/promise.js");

"use strict";

// Number of squares width and height
var GRID = 5;

var pad = function(n, width) {
    return n.length >= width ? n : new Array(width - n.length + 1).join("0") + n;
};

/**
 * Fill in a square on the canvas.
 */
var fill = function(svg, x, y, padding, size, color) {
    var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");

    rect.setAttribute("x", padding + x * size);
    rect.setAttribute("y", padding + y * size);
    rect.setAttribute("width", size);
    rect.setAttribute("height", size);
    rect.setAttribute("style", "fill: " + color);

    svg.appendChild(rect);
};

/**
 * Pick random squares to fill in.
 */
var generateIdenticon = function(key, padding, size, config) {

    var svg =  document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("version", "1.1");
    svg.setAttribute("viewBox", "0 0 " + size + " " + size);
    svg.setAttribute("preserveAspectRatio", "xMinYMin meet");
    svg.setAttribute("shape-rendering", "crispEdges");
    fill(svg, 0, 0, 0, size + 2*padding, config["avatar-bg"]);

    if (typeof key === null) {
        return svg;
    }

    Q.when(key, function(key) {
        var hash = pad((parseInt(key.substr(-16), 16) % Math.pow(2, 18)).toString(2), 18),
            index = 0;

        svg.setAttribute("data-hash", key);

        var i = parseInt(hash.substring(hash.length - 3, hash.length), 2),
            color = config["avatar-fg"][i % config["avatar-fg"].length];

        for (var x=0; x<Math.ceil(GRID/2); x++) {
            for (var y=0; y<GRID; y++) {

                if (hash.charAt(index) === "1") {
                    fill(svg, x, y, padding, 8, color);

                    // fill right sight symmetrically
                    if (x < Math.floor(GRID/2)) {
                        fill(svg, (GRID-1) - x, y, padding, 8, color);
                    }
                }
                index++;
            }
        }
    });

    return svg;
};

/* TODO: This function is currently unused and should be removed */
var generateBlank = function(height, width, config) {

    var blank = parseInt([
        0, 1, 1, 1, 1,
        1, 0, 1, 1, 0,
        1, 1, 1, 1, 1, /* purple: */ 0, 1, 0
    ].join(""), 2).toString(16);

    var el = generateIdenticon(blank, height, width, config);
    el.setAttribute("className", "blank"); // IE10 does not support classList on SVG elements, duh.

    return el;
};

module.exports = {
    generate: generateIdenticon,
    blank: generateBlank,
};


/***/ }),

/***/ "./isso/js/app/lib/promise.js":
/*!************************************!*\
  !*** ./isso/js/app/lib/promise.js ***!
  \************************************/
/***/ (function(module) {

"use strict";


var stderr = function(text) { console.log(text); };

var Promise = function() {
    this.success = [];
    this.errors = [];
};

Promise.prototype.then = function(onSuccess, onError) {
    this.success.push(onSuccess);
    if (onError) {
        this.errors.push(onError);
    } else {
        this.errors.push(stderr);
    }
};

var Defer = function() {
    this.promise = new Promise();
};

Defer.prototype = {
    promise: Promise,
    resolve: function(rv) {
        this.promise.success.forEach(function(callback) {
            window.setTimeout(function() {
                callback(rv);
            }, 0);
        });
    },

    reject: function(error) {
        this.promise.errors.forEach(function(callback) {
            window.setTimeout(function() {
                callback(error);
            }, 0);
        });
    }
};

var when = function(obj, func) {
    if (obj instanceof Promise) {
        return obj.then(func);
    } else {
        return func(obj);
    }
};

var defer = function() { return new Defer(); };

module.exports = {
    defer: defer,
    when: when,
};


/***/ }),

/***/ "./isso/js/app/lib/ready.js":
/*!**********************************!*\
  !*** ./isso/js/app/lib/ready.js ***!
  \**********************************/
/***/ (function(module) {

"use strict";


var loaded = false;
var once = function(callback) {
    if (! loaded) {
        loaded = true;
        callback();
    }
};

var domready = function(callback) {

    // HTML5 standard to listen for dom readiness
    document.addEventListener('DOMContentLoaded', function() {
        once(callback);
    });

    // if dom is already ready, just run callback
    if (document.readyState === "interactive" || document.readyState === "complete" ) {
        once(callback);
    }
};

module.exports = domready;


/***/ }),

/***/ "./isso/js/app/template.js":
/*!*********************************!*\
  !*** ./isso/js/app/template.js ***!
  \*********************************/
/***/ (function(module, __unused_webpack_exports, __webpack_require__) {

var utils = __webpack_require__(/*! app/utils */ "./isso/js/app/utils.js");

var tmpl_postbox = __webpack_require__(/*! app/templates/postbox */ "./isso/js/app/templates/postbox.js");
var tmpl_comment = __webpack_require__(/*! app/templates/comment */ "./isso/js/app/templates/comment.js");
var tmpl_comment_loader = __webpack_require__(/*! app/templates/comment-loader */ "./isso/js/app/templates/comment-loader.js");

"use strict";

var globals = {},
    templates = {};

var load_tmpl = function(name, tmpl) {
    templates[name] = tmpl;
};

var set = function(name, value) {
    globals[name] = value;
};

load_tmpl("postbox", tmpl_postbox);
load_tmpl("comment", tmpl_comment);
load_tmpl("comment-loader", tmpl_comment_loader);

set("humanize", function(date) {
    if (typeof date !== "object") {
        date = new Date(parseInt(date, 10) * 1000);
    }

    return date.toString();
});
set("datetime", function(date) {
    if (typeof date !== "object") {
        date = new Date(parseInt(date, 10) * 1000);
    }

    return [
        date.getUTCFullYear(),
        // getUTCMonth returns zero-based month!
        utils.pad(date.getUTCMonth() + 1, 2),
        // getUTCDay returns day of week, not month!
        utils.pad(date.getUTCDate(), 2)
    ].join("-") + "T" + [
        utils.pad(date.getUTCHours(), 2),
        utils.pad(date.getUTCMinutes(), 2),
        utils.pad(date.getUTCSeconds(), 2)
    ].join(":") + "Z";
});

var render = function(name, locals) {
    var rv, t = templates[name];
    if (! t) {
        throw new Error("Template not found: '" + name + "'");
    }

    locals = locals || {};

    var keys = [];
    for (var key in locals) {
        if (locals.hasOwnProperty(key) && !globals.hasOwnProperty(key)) {
            keys.push(key);
            globals[key] = locals[key];
        }
    }

    rv = templates[name](globals);

    for (var i = 0; i < keys.length; i++) {
        delete globals[keys[i]];
    }

    return rv;
};

module.exports = {
    set: set,
    render: render,
};


/***/ }),

/***/ "./isso/js/app/templates/comment-loader.js":
/*!*************************************************!*\
  !*** ./isso/js/app/templates/comment-loader.js ***!
  \*************************************************/
/***/ (function(module) {

var html = function (globals) {
  var comment = globals.comment;
  var pluralize = globals.pluralize;

  return "" +
"<div class='isso-comment-loader' id='isso-loader-" + comment.name + "'>"
+ "<a class='isso-load-hidden' href='#'>" + pluralize('comment-hidden', comment.hidden_replies) + "</a>"
+ "</div>"
};
module.exports = html;


/***/ }),

/***/ "./isso/js/app/templates/comment.js":
/*!******************************************!*\
  !*** ./isso/js/app/templates/comment.js ***!
  \******************************************/
/***/ (function(module) {

var html = function (globals) {
  var i18n = globals.i18n;
  var comment = globals.comment;
  var conf = globals.conf;
  var datetime = globals.datetime;
  var humanize = globals.humanize;

  var author = comment.author ? comment.author : i18n('comment-anonymous');
  var isPageAuthor = conf["page-author-hashes"].indexOf(comment.hash) > -1;
  var pageAuthorClass = (isPageAuthor ? " isso-is-page-author" : '');

  return "" +
"<div class='isso-comment" + pageAuthorClass + "' id='isso-" + comment.id + "' data-hash='" + comment.hash + "'>"
+ (conf.gravatar ? "<div class='isso-avatar'><img src='" + comment.gravatar_image + "'></div>" : '')
+ (conf.avatar ? "<div class='isso-avatar'><svg data-hash='" + comment.hash + "'</svg></div>" : '')
+ "<div class='isso-text-wrapper'>"
  + "<div class='isso-comment-header'>"
    + (comment.website
        ? "<a class='isso-author' href='" + comment.website + "' rel='nofollow'>" + author + "</a>"
        : "<span class='isso-author'>" + author + "</span>")
    + (isPageAuthor
        ? "<span class='isso-spacer'>&bull;</span>"
          + "<span class='isso-page-author-suffix'>" + i18n('comment-page-author-suffix') + "</span>"
        : '' )
     + "<span class='isso-spacer'>&bull;</span>"
     + "<a class='isso-permalink' href='#isso-" + comment.id + "'>"
       + "<time title='" + humanize(comment.created) + "' datetime='" + datetime(comment.created) + "'>" + humanize(comment.created) + "</time>"
     + "</a>"
     + "<span class='isso-note'>"
         + (comment.mode == 2 ? i18n('comment-queued') : (comment.mode == 4 ? i18n('comment-deleted') : ''))
     + "</span>"
  + "</div>" // .text-wrapper
  + "<div class='isso-text'>"
    + (comment.mode == 4 ? '<p>&nbsp;</p>' : comment.text)
  + "</div>" // .text
  + "<div class='isso-comment-footer'>"
     + "<a class='isso-reply' href='#'>" + i18n('comment-reply') + "</a>"
     + "<a class='isso-edit' href='#'>" + i18n('comment-edit') + "</a>"
     + "<a class='isso-delete' href='#'>" + i18n('comment-delete') + "</a>"
  + "</div>" // .isso-comment-footer
+ "</div>" // .text-wrapper
+ "<div class='isso-follow-up'></div>"
+ "</div>" // .isso-comment
};
module.exports = html;


/***/ }),

/***/ "./isso/js/app/templates/postbox.js":
/*!******************************************!*\
  !*** ./isso/js/app/templates/postbox.js ***!
  \******************************************/
/***/ (function(module) {

var html = function (globals) {
  var i18n = globals.i18n;
  var conf = globals.conf;
  var author = globals.author;
  var email = globals.email;
  var website = globals.website;
  var notify = conf["reply-notifications-default-enabled"] ? " checked" : '';

  return "" +
"<div class='isso-postbox'>"
 + "<div class='isso-form-wrapper'>"
   + "<div class='isso-textarea-wrapper'>"
    + "<textarea class='isso-textarea' rows='5' minlength='3' maxlength='65535' placeholder='" + i18n('postbox-text') + "'></textarea>"
    + "<div class='isso-preview'>"
      + "<div class='isso-comment'>"
        + "<div class='isso-text-wrapper'>"
          + "<div class='isso-text'></div>"
        + "</div>"
      + "</div>"
    + "</div>"
  + "</div>"
  + "<div class='isso-auth-section'>"
    + "<p class='isso-input-wrapper'>"
      + "<label for='isso-postbox-author'>" + i18n('postbox-author') + "</label>"
      + "<input id='isso-postbox-author' type='text' name='author' placeholder='" + i18n('postbox-author-placeholder') + "' value='" + (author ? author : '') + "' />"
    + "</p>"
    + "<p class='isso-input-wrapper'>"
      + "<label for='isso-postbox-email'>" + i18n('postbox-email') + "</label>"
      + "<input id='isso-postbox-email' type='email' name='email' placeholder='" + i18n('postbox-email-placeholder') + "' value='" + (email ? email : '') + "' />"
    + "</p>"
    + "<p class='isso-input-wrapper'>"
      + "<label for='isso-postbox-website'>" + i18n('postbox-website') + "</label>"
      + "<input id='isso-postbox-website' type='text' name='website' placeholder='" + i18n('postbox-website-placeholder') + "' value='" + (website ? website : '') + "' />"
    + "</p>"
    + "<p class='isso-post-action'>"
      + "<input type='submit' value='" + i18n('postbox-submit') + "' />"
    + "</p>"
    + "<p class='isso-post-action'>"
      + "<input type='button' name='preview' value='" + i18n('postbox-preview') + "' />"
    + "</p>"
    + "<p class='isso-post-action'>"
      + "<input type='button' name='edit' value='" + i18n('postbox-edit') + "' />"
    + "</p>"
  + "</div>"
  + "<div class='isso-notification-section'>"
    + "<label>"
      + "<input type='checkbox'" + notify + " name='notification' />" + i18n('postbox-notification')
    + "</label>"
  + "</div>"
+ "</div>"
+ "</div>"
};
module.exports = html;


/***/ }),

/***/ "./isso/js/app/utils.js":
/*!******************************!*\
  !*** ./isso/js/app/utils.js ***!
  \******************************/
/***/ (function(module) {

"use strict";


// return `cookie` string if set
var cookie = function(cookie) {
    return (document.cookie.match('(^|; )' + cookie + '=([^;]*)') || 0)[2];
};

var pad = function(n, width, z) {
    z = z || '0';
    n = n + '';
    return n.length >= width ? n : new Array(width - n.length + 1).join(z) + n;
};

// Normalize a BCP47 language tag.
// Quoting https://tools.ietf.org/html/bcp47 :
//   An implementation can reproduce this format without accessing
//   the registry as follows.  All subtags, including extension
//   and private use subtags, use lowercase letters with two
//   exceptions: two-letter and four-letter subtags that neither
//   appear at the start of the tag nor occur after singletons.
//   Such two-letter subtags are all uppercase (as in the tags
//   "en-CA-x-ca" or "sgn-BE-FR") and four-letter subtags are
//   titlecase (as in the tag "az-Latn-x-latn").
// We also map underscores to dashes.
var normalize_bcp47 = function(tag) {
    var subtags = tag.toLowerCase().split(/[_-]/);
    var afterSingleton = false;
    for (var i = 0; i < subtags.length; i++) {
        if (subtags[i].length === 1) {
            afterSingleton = true;
        } else if (afterSingleton || i === 0) {
            afterSingleton = false;
        } else if (subtags[i].length === 2) {
            subtags[i] = subtags[i].toUpperCase();
        } else if (subtags[i].length === 4) {
            subtags[i] = subtags[i].charAt(0).toUpperCase()
                + subtags[i].substr(1);
        }
    }
    return subtags.join("-");
};

// Safari private browsing mode supports localStorage, but throws QUOTA_EXCEEDED_ERR
var localStorageImpl;
try {
    localStorage.setItem("x", "y");
    localStorage.removeItem("x");
    localStorageImpl = localStorage;
} catch (ex) {
    localStorageImpl = (function(storage) {
        return {
            setItem: function(key, val) {
                storage[key] = val;
            },
            getItem: function(key) {
                return typeof(storage[key]) !== 'undefined' ? storage[key] : null;
            },
            removeItem: function(key) {
                delete storage[key];
            }
        };
    })({});
}

// Check if something is ready, and if not, register self as listener to be
// triggered once it is ready
var wait_for = function() {
    var listeners = [];
    var is_ready = false;
    return {
        is_ready: function(){return is_ready},
        register: function(listener) {
            // Ignore duplicate listeners
            if (listeners.indexOf(listener) < 0) {
                listeners.push(listener);
            };
        },
        reset: function() { is_ready = false },
        on_ready: function() {
            is_ready = true;
            for (var listener in listeners) {
                // Ignore dead listeners
                if (!listeners[listener]) {
                    continue;
                }
                // Run listener
                listeners[listener]();
            }
            // Clear listeners
            listeners = [];
        },
    };
};

module.exports = {
    cookie: cookie,
    localStorageImpl: localStorageImpl,
    normalize_bcp47: normalize_bcp47,
    pad: pad,
    wait_for: wait_for,
};


/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
var __webpack_exports__ = {};
// This entry need to be wrapped in an IIFE because it need to be isolated against other modules in the chunk.
!function() {
/*!**************************!*\
  !*** ./isso/js/embed.js ***!
  \**************************/
/*
 * Copyright 2014, Martin Zimmermann <info@posativ.org>. All rights reserved.
 * Distributed under the MIT license
 */

var domready = __webpack_require__(/*! app/lib/ready */ "./isso/js/app/lib/ready.js");
var config = __webpack_require__(/*! app/config */ "./isso/js/app/config.js");
var default_config = __webpack_require__(/*! app/default_config */ "./isso/js/app/default_config.js");
var i18n = __webpack_require__(/*! app/i18n */ "./isso/js/app/i18n.js");
var api = __webpack_require__(/*! app/api */ "./isso/js/app/api.js");
var isso = __webpack_require__(/*! app/isso */ "./isso/js/app/isso.js");
var $ = __webpack_require__(/*! app/dom */ "./isso/js/app/dom.js");
var template = __webpack_require__(/*! app/template */ "./isso/js/app/template.js");
var utils = __webpack_require__(/*! app/utils */ "./isso/js/app/utils.js");

"use strict";

template.set("conf", config);
template.set("i18n", i18n.translate);
template.set("pluralize", i18n.pluralize);

var isso_thread;
var heading;
var postbox;

// Track whether config has been fetched from server
var config_fetched = utils.wait_for();

function init() {
    config_fetched.reset()

    isso_thread = $('#isso-thread');
    heading = $.new('h4.isso-thread-heading');
    if (isso_thread === null) {
        return console.log("abort, #isso-thread is missing");
    }

    if (config["css"] && $("#isso-style") === null) {
        var style = $.new("link");
        style.id = "isso-style";
        style.rel ="stylesheet";
        style.type = "text/css";
        style.href = config["css-url"] ? config["css-url"] : api.endpoint + "/css/isso.css";
        $("head").append(style);
    }

    // Fetch config from server, will override any local data-isso-* attributes
    api.config().then(
        function (rv) {
            for (var setting in rv.config) {
                if (setting in config
                    && config[setting] != default_config[setting]
                    && config[setting] != rv.config[setting]) {
                    console.log("Isso: Client value '%s' for setting '%s' overridden by server value '%s'.\n" +
                                "Since Isso version 0.12.6, 'data-isso-%s' is only configured via the server " +
                                "to keep client and server in sync",
                                config[setting], setting, rv.config[setting], setting);
                }
                config[setting] = rv.config[setting]
            }

            // Depends on whether feed is enabled on server
            if (config["feed"] && $(".isso-feedlink") === null) {
                var feedLink = $.new('a', i18n.translate('atom-feed'));
                var feedLinkWrapper = $.new('span.isso-feedlink');
                feedLink.href = api.feed(isso_thread.getAttribute("data-isso-id"));
                feedLinkWrapper.appendChild(feedLink);
                isso_thread.append(feedLinkWrapper);
            }
            // Only insert elements if not already present, respecting Single-Page-Apps
            if (!$('h4.isso-thread-heading')) {
                isso_thread.append(heading);
            }
            postbox = new isso.Postbox(null);
            if (!$('.isso-postbox')) {
                isso_thread.append(postbox);
            } else {
                $('.isso-postbox').value = postbox;
            }
            if (!$('#isso-root')) {
                isso_thread.append('<div id="isso-root"></div>');
            }

            config_fetched.on_ready();
        },
        function(err) {
            console.log(err);
        }
    );

    window.addEventListener('hashchange', function() {
        if (!window.location.hash.match("^#isso-[0-9]+$")) {
            return;
        }

        var existingTarget = $(".isso-target");
        if (existingTarget != null) {
            existingTarget.classList.remove("isso-target");
        }

        try {
            $(window.location.hash + " > .isso-text-wrapper").classList.add("isso-target");
        } catch(ex) {
            // selector probably doesn't exist as element on page
        }
    });
}

function fetchComments() {

    var isso_root = $('#isso-root');
    if (!isso_root || !config_fetched.is_ready()) {
        config_fetched.register(fetchComments);
        return;
    }
    isso_root.textContent = '';


    api.fetch({
        tid: isso_thread.getAttribute("data-isso-id") || location.pathname,
        limit: config["max-comments-top"],
        nested_limit: config["max-comments-nested"],
        parent: null,
        sort: config["sorting"],
        offset: 0
    }).then(
        function (rv) {

            if (rv.total_replies === 0) {
                heading.textContent = i18n.translate("no-comments");
                return;
            }

            var count = rv.total_replies;
            rv.replies.forEach(function(comment) {
                isso.insert({ comment: comment, scrollIntoView: false, offset: 0 });
            });
            heading.textContent = i18n.pluralize("num-comments", count);

            if (rv.hidden_replies > 0) {
                isso.insert_loader(rv, rv.replies.length);
            }

            if (window.location.hash.length > 0 &&
                window.location.hash.match("^#isso-[0-9]+$")) {
                try {
                    $(window.location.hash).scrollIntoView();

                    // We can't just set the id to `#isso-target` because it's already set to `#isso-[number]`
                    // So a class `.isso-target` has to be used instead, and then we can manually remove the
                    // class from the old target comment in the `hashchange` listener.
                    $(window.location.hash + " > .isso-text-wrapper").classList.add("isso-target");
                } catch(ex) {
                    // selector probably doesn't exist as element on page
                }
            }
        },
        function(err) {
            console.log(err);
        }
    );
}

domready(function() {
    init();
    fetchComments();
});

window.Isso = {
    init: init,
    fetchComments: fetchComments
};

}();
/******/ })()
;
//# sourceMappingURL=embed.dev.js.map