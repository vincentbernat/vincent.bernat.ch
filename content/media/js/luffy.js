---
combine:
    files: luffy.*.js
    where: top
    remove: yes
---
/* Log errors to Google Analytics.
   See: http://www.thetaboard.com/blog/client-side-error-logging-with-google-analytics
*/
if (typeof(_gaq) !== 'undefined') {
    window.onerror = function(message, file, line) {
	var sFormattedMessage = '[' + file + ' (' + line + ')] ' + message;
	_gaq.push(['_trackEvent', 'Exceptions', 'Application',
		   sFormattedMessage, null, true]);
    }
}

$(function() {
    luffy.mathjax();
    luffy.effects();
    luffy.search();
    luffy.timeago();
    luffy.comments();
    luffy.gallery();
});
