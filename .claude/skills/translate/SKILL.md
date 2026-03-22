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
5. Do not summarize anything.

## Translation rules

- Keep all Markdown markup intact.
- Keep original link reference names and URLs unchanged.
- Do not translate code blocks or command examples.
- In French, footnote marks go **before** the punctuation.
- Avoid word-for-word translation: use idiomatic French and assume the reader is
  a native speaker.
- Avoid "anglicismes" when a proper French equivalent exists.
- Avoid "on" as a pronoun.
- Translate the `title` and `description` front matter fields.
- Keep `uuid`, `tags`, `cover`, and `attachments` fields unchanged.
