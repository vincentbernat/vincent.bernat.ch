/* When ready */
$(function() {
    /* Set appropriate height for rotated pages */
    $("#lf-page-1,#lf-page-2")
	.css("height",$("#lf-page").innerHeight());
    /* Animate the language box */
    $("#lf-translations").css('left',
			      '-' + $("#lf-translations").css('width'))
	.animate({left: 0}, 'slow');
})
