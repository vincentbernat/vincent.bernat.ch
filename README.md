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

### Poetry

Check oudated dependencies:

```
poetry show --outdated
```

Update a dependency:

```
poetry update --lock langcodes
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

### Translating

Using Claude 3.5 Sonnet, I use the following prompt, then copy/paste Markdown
content, with the exception of code blocks:

> Translate to French the following text, keep markdown markup, and enclose the
> result in a code block. For links, keep the original references.

### Editing

Using Claude 3.5 Sonnet, I use the following prompt, then copy/paste Markdown
content, with the exception of code blocks:

> Edit the following text, keep markdown markup, and enclode the result in a
> code block. There is no need to add comments. You can include very light
> stylistic edit but avoid using prnoun-verb contractions and keep a casual
> tone. The target is a technical audience who may not be English-native
> speakers (CEFR B2 level).
