# vincent.bernat.ch

This is the source code of my website. You can find the result at
<http://vincent.bernat.ch>. I am using [Hyde][hyde], an unmaintained
static website generator written in Python.

Licensing is described in `content/en/licenses.html`.

This site is hosted on NixOS instances. You may find the remaining
nginx configuration on [another Git repository][nixos] (the other
part is in `layout/nginx.j2`).

[hyde]: https://github.com/hyde/hyde
[cc1]: http://creativecommons.org/licenses/by-nc-sa/3.0/
[cc2]: http://creativecommons.org/licenses/by/3.0/
[nixos]: https://github.com/vincentbernat/nixops-take1/blob/master/tags/web.nix

## Various commands

### Build

```
nix develop
inv build
```

### uv

Check oudated dependencies:

```
uv lock --upgrade --dry-run
```

Update all dependencies:

```
uv lock --upgrade
```

Update only one dependency:

```
uv lock --upgrade-package lxml
```

### Yarn

Check oudated dependencies:

```
yarn outdated
```

Upgrade a dependency:

```
yarn upgrade-interactive --modules-folder ~/tmp/node_modules --ignore-scripts --latest
```

### Nix

Update nixpkgs:

```
nix flake update nixpkgs
```

### Git

Easy rebase of a WIP progress + checkout:

```
git rebase latest article/something
```

## Use of an LLM as an editor

I write article in English, then translate it to French. This seems easier for
me than the other direction. As I am not a native English speaker, I am using
LLMs to edit the English content or to translate to French. Since French is my
mother tongue, I edit the French result myself.

Using Claude 4.1 Opus, I use the following prompts, then copy/paste Markdown
content, with the exception of code blocks.

### Translating

> Translate to French the following text, keep markdown markup, and enclose the
> result in a code block. For links, keep the original references. In French,
> footnote marks should be placed before the punctuation. Avoid word-for-word
> translationa and feel free to choose more idiomatic concepts. I prefer to
> avoid "anglicismes".

It should be possible to have a [more guided prompt][], but for now, this is
enough for me: being a French native speaker, I can proofread the result myself.

[more guided prompt]: https://www.gally.net/temp/20250201sampletranslationprompt.html

### Editing

> Edit the following text, keep markdown markup, and enclose the result in a
> code block. There is no need to add comments. The target is a technical
> audience who may not be English-native speakers (CEFR B2 level). You can
> include light stylistic edit but avoid using pronoun-verb contractions and
> keep a casual tone. You can also suppress a passive voice, remove superfluous
> words, use more descriptive words, and break a long sentence into smaller
> ones. Prefer the present tense. I am not an English-native speaker myself, so
> you can also fix common mistakes done by people like me, notably simple past
> vs past perfect.

I am unsure this prompt is best. I don't like AI that are putting words in my
mouth, hence the above prompt with minimal editing. However, I am not that good
at technical writing either. There are a few interesting resources around it
like [The Craft of Writing Effectively][] ([handouts][h1]) and [Refactoring
English][].

The first video is about challenging the readers and changing their ideas to
create tangible value for them to care about your own ideas. You should use
language that convey instability, tension, or potential costs and benefits to
engage them meaningfully. The introduction should expose a problem with three
components: an instability, the consequences of this instability (and associated
costs or benefits), and readers who will be interested in the costs or benefits.
It should not try to leverage novelty or originality of a work as it fails to
engage the readers who may not care about this. “Move forward from instability
to stability.” There is another related video, [Writing Beyond the Academy][]
([handouts][h2]).

The second book is a work in progress. You need to value the readers' time and
evaluate if each sentence is worth their time: get to the point quickly, be
clear, use a dynamic language, cut down extra words and filler phrases,
organize. Notably, you need to work on the hook of your article: the title and
the first three sentences. Telling a story is also a way to engage the reader a
bit more, as well as adding some pictures. The author is known to hire
illustrators. As for writing tips, the author mentions the use of descriptive
verbs to drive a sentence (e.g. use "authenticate" instead of "provide
authentication"), staying positive, avoiding passive voice, and improving
brevity.

[the craft of writing effectively]: https://www.youtube.com/watch?v=vtIzMaLkCaM
[h1]: https://ldmce.wordpress.com/wp-content/uploads/2020/09/emerg-leaders-acad-14.pdf
[writing beyond the academy]: https://www.youtube.com/watch?v=aFwVf5a3pZM
[h2]: https://ldmce.wordpress.com/wp-content/uploads/2020/09/emerg-leaders-non-acad-14.pdf
[refactoring english]: https://refactoringenglish.com/
