---
extends: false
ai-usage: disabled
---
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:xhtml="http://www.w3.org/1999/xhtml" version="1.0">
  <xsl:output method="html" encoding="UTF-8" indent="no"/>
  <xsl:template match="/atom:feed">
    <html class="nojs rss">
      <xsl:attribute name="lang">
        <xsl:value-of select="@xml:lang"/>
      </xsl:attribute>
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width,initial-scale=1"/>
        <title>
          <xsl:value-of select="atom:title"/>
        </title>
        <link rel="icon" href="{{ media_url('images/favicon.png') }}"/>
        <link rel="stylesheet" href="{{ media_url('css/luffy.css') }}"/>
        <link rel="stylesheet" href="{{ media_url('css/luffy1.code.css') }}"/>
        <link rel="stylesheet" href="{{ media_url('css/luffy1.toc.css') }}"/>
        <link rel="stylesheet" href="{{ media_url('css/luffy1.media.css') }}"/>
        <link rel="stylesheet" href="{{ media_url('css/luffy1.atom.css') }}"/>
        <link rel="alternate" type="application/atom+xml">
          <xsl:attribute name="href">
            <xsl:value-of select="atom:link[@rel='self']/@href"/>
          </xsl:attribute>
        </link>
        <link rel="canonical">
          <xsl:attribute name="href">
            <xsl:value-of select="atom:link[@rel='self']/@href"/>
          </xsl:attribute>
        </link>
      </head>
      <body>
        <main class="lf-main">
          <div class="lf-text">
{% set feed = base ~ "/" ~ resource.meta.language ~ "/blog/atom.xml" %}
{% filter markdown|typogrify|clean_rss %}
{% if resource.meta.language == "fr" %}
La façon la plus simple d'être averti de la publication de nouveaux articles est
de [s'abonner à ce flux RSS][rss] dans votre lecteur favori. Si vous ne disposez
pas encore du lecteur adéquat, il existe de nombreuses applications à cet effet,
notamment [Miniflux][] ou [NewsBlur][]. Certains services, tels que
[Blogtrottr][] ou [FeedRabbit][], permettent même de le recevoir par courrier
électronique. Vous pouvez également me suivre sur [Mastodon][] ou [Bluesky][].
{% else %}
To know when I publish new articles, subscribe to [this RSS feed][rss] in your
favorite reader. If you don't have one yet, many applications exist, including
[Miniflux][] and [NewsBlur][]. Some services, like [Blogtrottr][] or
[FeedRabbit][], even deliver it to your inbox. You can also follow me on
[Mastodon][] or [Bluesky][].
{% endif %}

[rss]: {{ feed }}
[FeedRabbit]: https://feedrabbit.com/?url={{ feed }}
[Blogtrottr]: https://blogtrottr.com/?subscribe={{ feed }}
[Miniflux]: https://miniflux.app/ "Miniflux"
[NewsBlur]: https://www.newsblur.com/ "NewsBlur"
[Bluesky]: https://bsky.app/profile/{{ resource.meta.bluesky }}
[Mastodon]: {{ resource.meta.mastodon|mastodon_href }}
{% endfilter %}
          </div>
          <xsl:apply-templates select="atom:entry"/>
        </main>
        <nav id="lf-navbar" xml:space="preserve">
          {% filter indent(10) %}{% include "menu.j2" %}{% endfilter %}

        </nav>
        <footer xml:space="preserve">
          {% filter indent(10) %}{% include "footer.j2" %}{% endfilter %}

        </footer>
        <script src="{{ media_url('js/luffy.js') }}" type="module"></script>
      </body>
    </html>
  </xsl:template>
  <xsl:template match="atom:entry">
    <article>
      <header>
        <h1>
          <a>
            <xsl:attribute name="href">
              <xsl:value-of select="atom:link[@rel='alternate']/@href"/>
            </xsl:attribute>
            <xsl:value-of select="atom:title"/>
          </a>
        </h1>
        <h2>
          <xsl:value-of select="atom:author/atom:name"/>
          <time>
            <xsl:attribute name="datetime">
              <xsl:value-of select="atom:updated"/>
            </xsl:attribute>
            <xsl:value-of select="substring(atom:updated, 1, 10)"/>
          </time>
        </h2>
      </header>
      <div class="lf-text">
        <xsl:copy-of select="atom:content/xhtml:div/node()"/>
      </div>
    </article>
  </xsl:template>
</xsl:stylesheet>
