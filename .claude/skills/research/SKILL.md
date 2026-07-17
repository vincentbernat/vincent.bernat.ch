---
name: research
description: >
  Researches the topic of a blog article to verify claims, identify gaps,
  and suggest additional citations. Triggers when the user mentions
  "research", "verify", "find references", "citations", "review", or asks to
  strengthen or review the content of an article.
allowed-tools: WebFetch, WebSearch, Read, Grep, Glob, Bash(man *)
---

# Research an article topic

## Input

If the user does not provide a specific article to research, look at the current
status of the Git repository to check which article the user is currently
editing. The article may contain some hints on the target audience and goals as
HTML comments at the beginning.

## Steps

1. Read the article to understand the topic, claims, and existing references.
2. Search the web to:
   - Verify that technical claims are accurate and up-to-date.
   - Identify important aspects the article may have missed.
   - Find authoritative sources that could strengthen it (official
     documentation, RFCs, man pages, research papers, well-known blog posts).
3. Produce a report (do **not** modify the article).

## Report format

- Flag any claims that appear incorrect or outdated, with evidence.
- Suggest topics or angles the article could address to be more complete or
  useful.
- Propose additional references, each with a brief explanation of what it adds.
  Format them as Markdown link reference-style links ready to insert. Prefer
  primary sources (official docs, RFCs) over secondary ones.
