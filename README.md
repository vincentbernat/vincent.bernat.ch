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
[nixos]: https://github.com/vincentbernat/nixops-take1/blob/master/web.nix

## Various commands

### Build

```
nix develop
inv build
```

### Poetry

Check oudated dependencies:

```
nix run .#poetry -- show --outdated
```

Update a dependency:

```
nix run .#poetry -- update --lock langcodes
```

### Yarn

Check oudated dependencies:

```
nix run .#yarn -- outdated
```

Upgrade a dependency:

```
nix run .#yarn -- upgrade-interactive --modules-folder ~/tmp/node_modules --ignore-scripts --latest
```

### Nix

Update nixpkgs:

```
nix flake lock --update-input nixpkgs
```

### Git

Easy rebase of a WIP progress + checkout:

```
git rebase latest article/something
```
