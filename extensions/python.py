from hyde.plugin import Plugin

SHEBANG = "#!python\n"


class PythonPlugin(Plugin):
    """Execute resources starting with `#!python` as Python scripts.

    Such a resource defines a `run(site, resource)` function whose return value
    becomes the resource's content (computed in `text_resource_complete`).
    """

    def begin_text_resource(self, resource, text):
        if not text.startswith(SHEBANG):
            return
        namespace = {}
        exec(text, namespace)
        return namespace["run"](self.site, resource)
