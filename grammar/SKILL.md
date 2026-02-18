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
4. Summarize the changes.

Do not modify code blocks.
