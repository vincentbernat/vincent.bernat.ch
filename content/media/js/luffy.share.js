/* Share with share API */

luffy.s.push(function() {
    if (navigator.share) {
        var mail = document.querySelector('#lf-share .lf-sprite-mail'),
            share = document.querySelector('#lf-share .lf-sprite-share'),
            url = document.querySelector('link[rel=canonical]'),
            title = document.querySelector('meta[name="og:title"]');
        if (!mail || !share || !url || !title) {
            return;
        }
        share.addEventListener('click', function(event) {
            event.preventDefault();
            navigator.share({
                title: title.content,
                url: url.href
            });
        }, true);
        mail.parentNode.style.display = 'none';
        share.parentNode.style.display = 'inline';
    }
});
