---
name: updates
description: >
  Checks available updates for Python (uv) and JavaScript (npm) packages,
  reads their changelogs, and tells if each update is worth it and if the
  code needs changes. Triggers when the user asks to check for package,
  dependency, JavaScript, npm, Python or uv updates.
---

# Check package updates

## Input

No input. Run `uv lock --upgrade --dry-run` and `npm outdated` to check what
could be updated. Unless something break, I prefer things to be up-to-date.

Don't update anything: don't run `uv lock`, `npm update` or `npm install`.
The user does it.

## Packages to ignore

- `@svta/*` packages are pinned on purpose to match hls.js. Skip them.

## Steps

1. Read `pyproject.toml` and `package.json` to know the version constraints. A
   version shown as "Latest" but not "Wanted" by npm needs a change in
   `package.json` (for example `~1.0.0` or `^0.18.0`). Same for a Python major
   version outside a `==3.*` constraint. Newer releases than the ones shown may
   exist: `min-release-age` in `.npmrc` and `exclude-newer` in `pyproject.toml`
   hide recent ones. This is on purpose. Don't suggest them.
2. For each package, find if it is a direct dependency or only a transitive
   one (look at `uv.lock` or `package-lock.json`). For transitive ones (for
   example numpy or fonttools from matplotlib, ast-serialize from mypy), a
   short look at the changelog is enough.
3. Check each direct dependency with its own subagent (Agent tool,
   `general-purpose` type, Sonnet model). Start them all in one message so
   they run in parallel. Give each one the package name, the current and
   latest versions, and steps 4 to 6 below. Tell them to ignore versions after
   the latest one. Ask for a short answer: breaking changes that hit us (with file and
   line), useful new features, security fixes. Look at the transitive ones
   yourself. Then check the answers that ask for a code change before you
   report them.
4. Fetch the changelog for every version between the current one and the
   latest one, not only the latest. Good sources:
   - GitHub releases page when it has notes. It is often easier to read.
   - GitHub `CHANGELOG.md` or `NEWS.rst`. Use the raw URL
     (`raw.githubusercontent.com`) with curl when the GitHub page does not
     render.
   - Read-the-docs release notes (for example Pillow).
   - For packages from a monorepo (like `@csstools/*`), the changelog is in
     the plugin directory.
   - With no changelog, use the commit log between the two tags.
5. For each breaking change, deprecation or behavior change, search the code
   (`ssg/`, `content/media/css/`, `content/media/js/`, `layout/`, `flake.nix`)
   to see if we are affected. Check how the package is called: options passed,
   functions used, CSS features used. Some tools come from Nix and not from
   uv or npm (check `flake.nix`).
6. Check new features that we could use to simplify our code, for example a
   feature we implemented ourselves.

## Output

Group packages by ecosystem (Python, then JavaScript). For transitive
packages, one line each is enough. For each direct package, give:

- current and latest versions,
- a short summary of what changed that matters to us,
- if it is worth updating (security fixes, bug fixes that hit us, useful
  features, or nothing relevant),
- what to change in our code or in the version constraints, if anything.

End with a short list of the commands the user runs to apply updates
(mandatory and optionals). npm commands must use `--package-lock-only`:
direnv builds `node_modules` with Nix from `package-lock.json`. When a
constraint in `package.json` needs a change, don't ask to edit it: use `npm
install --package-lock-only pkg@~1.1.0` with the new range, keeping the
existing prefix (`~` or `^`). npm writes the range as given. Then `npm update
--package-lock-only` for the rest. Keep it short and skip changes that don't
concern us.
