---
name: edit
description: >
  Proofreads and lightly edits an English blog article for clarity, style,
  and grammar. Triggers when the user mentions "edit", "proofread",
  "review writing", or asks to improve the prose of an article in
  content/en/.
---

# Edit an English article

## Input

If the user does not provide, look at the current status of the Git repository
to check which article the user is currently editing.

## Steps

1. Read the article.
2. Edit the content following the rules below. Do not modify code blocks.
3. Apply the edits directly to the file.
4. Summarize the changes.

## Editing rules

- Keep all Markdown markup intact.
- Target audience: technical readers who may not be native English speakers
  (CEFR B2 level).
- Apply light stylistic edits only. Do not rewrite or restructure.
- Avoid pronoun-verb contractions (write "do not", not "don't").
- Keep a casual, conversational tone.
- Suppress passive voice where possible.
- Remove superfluous words and filler phrases.
- Use descriptive verbs (e.g. "authenticate" instead of "provide
  authentication").
- Break long sentences into shorter ones.
- Prefer the present tense.
- Fix common non-native mistakes, notably simple past vs. past perfect.

The following words are forbidden because what is obvious for someone may not be
for someone else!

- obviously
- basically
- simply
- clearly
- everyone knows

## About the introduction

The editing should follow these principles from [The Craft of Writing
Effectively][] ([handouts][h1]):

- **Challenge the reader**: use language that conveys instability, tension,
  or potential costs and benefits to engage them meaningfully.
- **Introduction structure**: expose a problem with three components: an
  instability, its consequences (costs or benefits), and readers who care
  about those costs or benefits. Do not rely on novelty or originality to
  engage readers.
- **Value the reader's time**: get to the point quickly, be clear, use
  dynamic language, cut extra words and filler phrases, organize well.
- **Work on the hook**: the title and the first three sentences matter most.
  
If the user specifically asks to focus on the introduction, apply these
principles to rewrite the introduction.

[the craft of writing effectively]: https://www.youtube.com/watch?v=vtIzMaLkCaM
[h1]: https://ldmce.wordpress.com/wp-content/uploads/2020/09/emerg-leaders-acad-14.pdf
