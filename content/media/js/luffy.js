---
combine:
    files: luffy.*.js
    where: top
    remove: yes
uses_template: true
---

$(function() {
    luffy.mathjax();
    luffy.effects();
    luffy.search();
    luffy.timeago();
    luffy.comments();
    luffy.gallery();
});
{% if site.config.mode == "development" %}
yepnope('{{ media_url("js/hashgrid.js") }}');
{% endif %}
