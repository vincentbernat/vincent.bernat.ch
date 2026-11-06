---
name: discussions
description: >
  Finds discussions of blog articles on Hacker News and Lobsters, and adds an
  update note linking to them in both English and French versions. Triggers
  when the user mentions "discussions", "Hacker News", "HN", "Lobsters", or
  asks to link to comments about an article.
allowed-tools: Read, Edit, Grep, Glob, Bash(curl -s https://hn.algolia.com/*), Bash(curl -s https://lobste.rs/*)
---

# Link to discussions of an article

## Input

The user may give one or several articles, or ask for all of them. If the user
gives nothing, look at the current status of the Git repository to check which
article the user is currently editing.

For each English article in `content/en/blog/`, find its French version in
`content/fr/blog/` by matching the `uuid` in the front matter. The slug may
differ.

Skip a site when the article already links to it (`news.ycombinator.com`,
`lobste.rs`).

## Find the discussions

- **Hacker News**: use the Algolia API:
  `curl -s "https://hn.algolia.com/api/v1/search?query=SLUG&restrictSearchableAttributes=url&tags=story"`.
  Each hit has `objectID`, `num_comments`, and `url`. Link to
  `https://news.ycombinator.com/item?id=OBJECTID`.
- **Lobsters**: list stories per domain with
  `curl -s https://lobste.rs/domains/vincent.bernat.ch/page/N.json`, N starting
  at 1, until the page is empty. Each story has `url`, `comment_count`, and
  `comments_url`. Link to `comments_url`. Fetch each page once, even for
  several articles.

Skip a thread with less than 10 comments.

## Write the update

Add the note at the end of the article content, before the abbreviations
(`*[...]: ...`) and the link references. If there is already an update about
discussions, extend it instead. Add the link references at the end of the file,
after the existing ones, with `[Hacker News]` and `[Lobsters]` as labels, in
this order.

The adverb depends on the thread with the most comments:

| Comments | English            | French                  |
| -------- | ------------------ | ----------------------- |
| 10–24    | briefly discussed  | brièvement discuté      |
| 25–39    | discussed          | discuté                 |
| 40–79    | widely discussed   | longuement discuté      |
| 80+      | heavily discussed  | abondamment discuté     |

Use the current month for the date. Wrap lines at 80 columns. Use the same links
in both languages.

English:

```markdown
!!! "Update (2026-10)"
    This post was widely discussed on [Hacker News][] and [Lobsters][].

[Hacker News]: https://news.ycombinator.com/item?id=16914764
[Lobsters]: https://lobste.rs/s/5cdd1k/more_privacy_friendly_blog
```

French:

```markdown
!!! "Mise à jour (10.2026)"
    Cet article a été longuement discuté sur [Hacker News][] et [Lobsters][].

[Hacker News]: https://news.ycombinator.com/item?id=16914764
[Lobsters]: https://lobste.rs/s/5cdd1k/more_privacy_friendly_blog
```

If a label is already used in the article for another link, pick another label.
If an article has several discussions, link them by adding some words, like
this:

```markdown
!!! "Update (2026-10)"
    This post was widely discussed on [Hacker News][HN1] [several][HN2]
    [times][HN3].

[HN1]: https://news.ycombinator.com/item?id=16914764
[HN2]: https://news.ycombinator.com/item?id=16914765
[HN3]: https://news.ycombinator.com/item?id=16914767
```

## Report

End with a short table: article, site, comments, link. List articles where
nothing was found and threads skipped for having too few comments.
