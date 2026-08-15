# vincent.bernat.ch

This is the source code of my website. You can find the result at
<http://vincent.bernat.ch>. I am using [Hyde][hyde], an unmaintained static
website generator written in Python. Likely, I would need to switch to another
project, either [Nikola](https://getnikola.com/) or [doit](https://pydoit.org/),
which is used by Nikola to build a SSG.

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

### npm

`--package-lock-only` updates `package.json`/`package-lock.json` without
touching the Nix-managed `node_modules` symlink. Nix rebuilds it on the next
`nix develop`.

Check oudated dependencies:

```
npm outdated
```

Add or upgrade a dependency:

```
npm install --package-lock-only katex@latest
```

Update all dependencies:

```
npm update --package-lock-onlyx
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

## LLM skills

I write articles in English, then translate them to French. As I am not
a native English speaker, I use LLMs to edit the English content and to
translate to French. Since French is my mother tongue, I proofread the
French result myself.

The `skills/` directory contains [Agent Skills][] for these tasks:

- **`translate`**: translate an English article to French
- **`edit`**: proofread and lightly edit an English article
- **`research`**: research an article's topic, verify claims, and suggest
  additional citations

I do not let LLMs write content outside light editing and translation.

[agent skills]: https://agentskills.io/
