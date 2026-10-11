"""Tasks to build the site.

Task names are "<kind>:<path>". doit also defines one task per kind to run all
the tasks of this kind. "doit list" describes them.
"""

# Kinds with several tasks, with their description and if they are only for
# production
GROUPS = {
    "copy": ("copy files as is", False),
    "media": ("process stylesheets, scripts and other text media", False),
    "image": ("generate images (SVG, resized images, thumbnails)", False),
    "cover": ("generate cover images", False),
    "article": ("render articles of blog posts", False),
    "fragment": ("render articles of other pages", False),
    "page": ("render pages", False),
    "subset": ("subset fonts", True),
    "font": ("publish fonts with a hashed name", True),
    "asset": ("publish stylesheets and scripts with a hashed name", True),
    "optimize": ("publish optimized images with a hashed name", True),
}

# Kinds with one task
SINGLES = {
    "pagefind-js": ("extract the pagefind library", False),
    "pagefind": ("build search index", False),
    "glyphs": ("collect glyphs used in articles", True),
    "bundle-sizes": ("report sizes of stylesheets, scripts and fonts", True),
    "prune": ("remove obsolete files", False),
}


def summary(production):
    """One task per kind, for "doit list" without planning the build."""
    for basename, (doc, only) in (GROUPS | SINGLES).items():
        if production or not only:
            yield {"basename": basename, "name": None, "doc": doc}
