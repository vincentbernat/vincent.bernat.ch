---
name: edit
description: >
  Proofreads and lightly edits an English blog article for clarity, style,
  and grammar. Triggers when the user mentions "edit", "proofread",
  or asks to improve the prose of an article in content/en/.
---

# Edit an English article

## Input

If the user does not provide, look at the current status of the Git repository
to check which article the user is currently editing. The article may contain
some hints on the target audience and goals as HTML comments at the beginning.

## Steps

1. Read the article.
2. Edit the content following the rules below. Do not modify code blocks.
3. Apply the edits directly to the file.
4. Disclose AI usage in the frontmatter.
5. Only summarize notable changes.
6. Propose a title

## Editing rules

- Keep all Markdown markup intact.
- Target audience: technical readers who may not be native English speakers
  (CEFR B2 level).
- Apply light stylistic edits only. Do not rewrite or restructure.
- Keep a casual, conversational tone.
- Suppress passive voice where possible, notably when the actor doing the action
  is known.
- Break long sentences into shorter ones.
- Prefer the present tense.
- Do not water down a sentence.
- Remove superfluous words and filler phrases. Be suspicious of adverbs and
  adjectives when they bring nothing to the verb and the noun. Be cautious when
  there are too many prepositions.
- Use descriptive verbs (e.g. "authenticate" instead of "provide
  authentication"). Do not flatten a descriptive verb into a bland one like
  "is". Avoid verbs with a preposition.
- Don't put "however" as the beginning of a sentence. "But", "yet", "still", and
  "instead", can be used instead.
- Prefer "that" to "which", except if a comma is needed and in this case,
  "which" is more correct.

The following words are forbidden because what is obvious for someone may not be
for someone else: "obviously", "basically", "simply", "clearly", and "everyone
knows".

For French, we follow “Lexique des règles typographiques en usage à l'Imprimerie
nationale.” For English, this is “The Chicago Manual of Style” but keep
contractions.

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

## About the title and description

The title is the strongest part of the hook (see above). Propose a few
alternatives and recommend one.

- Write for a broad technical audience, such as Hacker News, Lobsters, LinkedIn,
  not only for people who already know the project. Lead with the universal
  concept and the techniques that draw curiosity. Push too specific jargon in
  the description if it is still important.
- Be concrete and specific. State the technique or the result, not a vague
  promise.
- Keep it honest: the title should cover what the article actually delivers, not
  oversell one part.

The description (used for social networks and as the meta description) must
complement the title, not repeat it. The reader often sees both together, so the
description should add what the title leaves out. Keep it short enough to read
in a link preview.

## Disclose AI usage

To disclose AI usage in the frontmatter, add an `ai-usage` key with
`Copyediting` or `Révision linguistique` (depending on the language of the
document) with your model name between parentheses, e.g. `(Claude Opus 4.7)`. If
the key already exists, update it only if it's not a translation.
