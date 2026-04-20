---
name: grammar
description: >
  Proofreads an article for grammar mistakes. Triggers when user
  mentions "grammar", or asks to check for "typos".
---

# Grammar check for French or English

## Input

If the user does not provide, look at the current status of the Git repository
to check which article the user is currently editing. The article can be in
French (in content/fr/) or English (in content/en/).

## Steps

1. Read the article.
2. Check and fix typos and grammar mistakes in the language of the article.
3. Apply the edits directly to the file.
4. Disclose AI usage in the frontmatter.
5. Only summarize notable changes. It's OK to not summarize anything at all.

Do not modify code blocks. For French, we follow “Lexique des règles
typographiques en usage à l'Imprimerie nationale.” For English, this is “The
Chicago Manual of Style” but keep contractions.

To disclose AI usage in the frontmatter, add an `ai-usage` key with `Grammar
check` or `Vérification grammaticale` (depending on the language of the
document) with your model name between parentheses, e.g. `(Claude Opus 4.7)`. If
the key already exists, update it only if it's already a grammar check,
otherwise leave it untouched.
