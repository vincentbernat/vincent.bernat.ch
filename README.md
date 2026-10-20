# vincent.bernat.ch

This is the source code of my website. You can find the result at
<http://vincent.bernat.ch>. It is built by a small static site generator in
`ssg/`, using [doit][] to track dependencies and to build in parallel.

Licensing is described in `content/en/licenses.html`.

This site is hosted on NixOS instances. You may find the remaining
Caddy configuration on [another Git repository][nixos] (the other
part is in `layout/caddy.j2`).

[doit]: https://pydoit.org/
[cc1]: http://creativecommons.org/licenses/by-nc-sa/3.0/
[cc2]: http://creativecommons.org/licenses/by/3.0/
[nixos]: https://github.com/vincentbernat/nixops-take1/blob/master/tags/web.nix

## Various commands

### Build

```
nix develop
doit serve            # development build, served on http://localhost:8080
doit publish          # production build, review and commit in .final
doit push             # deploy
```

`doit` alone builds for development (in `.out`), `doit mode=prod` for
production (in `.final`). Builds are incremental and run in parallel in a
sandbox. `doit list` lists the commands.

Each task declares the files known before it runs, like its source, as
`file_dep`. While it runs, it also records what it reads: images, layouts, the
metadata of other pages, tools, environment variables, and the build code. Each
read is stored in doit's database with a digest. On the next build, the task
runs again when one of these digests changes. The kinds of recorded keys are
listed in `ssg/deps.py`.

Declared and recorded files are compared the same way: a file with the same
modification time did not change, a file with another size did. Otherwise, the
digest of its content decides, with xxHash (XXH3, 128 bits). For a file in git
annex, the name of the annex key is used instead of the content.

To check dependencies:

```
doit why page:en/blog/2026-spanning-tree.html
doit why page:en/blog/2026-spanning-tree.html mode=prod
```

For profiling:

```
doit profile=true mode=prod -a
python -m pstats .cache/ssg/production/profile.prof
nix run nixpkgs#gprof2dot -- -f pstats .cache/ssg/production/profile.prof | dot -Tsvg -o profile.svg
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
npm update --package-lock-only
```

### Nix

Update nixpkgs:

```
nix flake update nixpkgs
```

### Git

Easy rebase of a WIP progress + checkout:

```
git rebase main article/something
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
