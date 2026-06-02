from hyde.plugin import Plugin

SHEBANG = "#!python\n"


class PythonPlugin(Plugin):
    """Execute resources starting with `#!python` as Python scripts.

    Such a resource defines a `run(site, resource)` function whose return value
    becomes the resource's content (computed in `text_resource_complete`).

    In `begin_site`, these resources are moved onto the root content node so the
    generator emits them before any other node: hyde walks nodes sorted by path
    and yields the root first, which guarantees a dynamic resource is built
    before the pages referencing it (e.g. for image dimensioning).
    """

    def begin_site(self):
        root = self.site.content
        dynamic = []
        for node in root.walk():
            if node is root:
                continue
            for resource in node.resources:
                source = resource.source_file
                if source.is_binary:
                    continue
                try:
                    with open(source.path, encoding="utf-8") as f:
                        head = f.read(len(SHEBANG))
                except UnicodeDecodeError:
                    continue
                if head == SHEBANG:
                    dynamic.append((node, resource))
        for node, resource in dynamic:
            node.resources.remove(resource)
            root.resources.append(resource)
            resource.node = root

    def text_resource_complete(self, resource, text):
        if not text.startswith(SHEBANG):
            return
        namespace = {}
        exec(text, namespace)
        return namespace["run"](self.site, resource)
