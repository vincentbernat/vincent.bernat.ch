/* On errors, forward to Google Analytics */
if (typeof(_gaq) !== 'undefined') {
    window.onerror = function(message, file, line) {
	_gaq.push(['_trackEvent', 'Errors',
		   file + ':' + line,
		   message + '']);
    }
}
