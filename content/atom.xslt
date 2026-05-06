<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:xhtml="http://www.w3.org/1999/xhtml" version="1.0">
  <xsl:output method="html" encoding="UTF-8" indent="no"/>
  <xsl:template match="/atom:feed">
    <html>
      <xsl:attribute name="lang">
        <xsl:value-of select="@xml:lang"/>
      </xsl:attribute>
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width,initial-scale=1"/>
        <title>
          <xsl:value-of select="atom:title"/>
        </title>
        <link rel="stylesheet" href="{{ media_url('css/luffy.css') }}"/>
        <link rel="stylesheet" href="{{ media_url('css/luffy1.atom.css') }}"/>
        <link rel="alternate" type="application/atom+xml">
          <xsl:attribute name="href">
            <xsl:value-of select="atom:link[@rel='self']/@href"/>
          </xsl:attribute>
        </link>
      </head>
      <body>
        <main class="lf-main">
          <xsl:apply-templates select="atom:entry"/>
        </main>
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
