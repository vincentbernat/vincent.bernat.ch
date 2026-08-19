---
name: translate
description: >
  Translates an English blog article to French. Triggers when the user
  mentions "translate", "French version", or asks to create a
  content/fr/ counterpart of an English article.
---

# Translate an article to French

## Input

If the user does not provide a specific article to translate, look at the
current status of the Git repository to check which article the user is
currently editing.

## Steps

1. Read the English article.
2. Determine the French article path: replace `content/en/` with `content/fr/`.
   The filename may differ (French slug), so match by `uuid` in the front matter
   if a French version already exists. If the English version is `wip.html`,
   then the French version uses the same name.
3. Translate the article content following the rules below.
4. If a French article already exists, update its content. Otherwise, create a
   new file with an appropriate French slug.
5. Disclose AI usage.
6. Do not summarize anything.

## Translation rules

- Keep all Markdown markup intact.
- Keep original link reference names and URLs unchanged.
- Point internal links (`[[en/blog/…]]`) to the French counterpart when it
  exists and translate their title attribute.
- Do not translate code blocks or command examples, but translate the comments
  inside them.
- Drop the HTML comment describing the target audience at the top of the
  article: it is a note for the author.
- In French, footnote marks go **before** the punctuation.
- Avoid word-for-word translation: use idiomatic French and assume the reader is
  a native speaker.
- Avoid "anglicismes" when a proper French equivalent exists.
- Put the English words kept in the French text in italics, including inside
  guillemets, like « *edge port* ». Proper nouns, acronyms, and titles of works
  do not need italics. A term already in bold stays in bold: never combine bold
  and italics.
- Avoid "on" as a pronoun.
- Use « guillemets » with a plain space inside
- Use a plain space as thousands separator.
- Avoid em dashes: French prose uses a colon, a comma, or even parentheses.
- Translate the `title` and `description` front matter fields.
- Keep `uuid`, `tags`, `cover`, and `attachments` fields unchanged.

## Disclose AI usage

To disclose AI usage in the frontmatter, add an `ai-usage` key with `Translated
from French` or `Traduit de l'anglais` with your model name between parentheses,
e.g. `(Claude Opus 4.7)`. If the key already exists, ask what to do.
