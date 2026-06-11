from hyde.plugin import Plugin
from fswrap import File

SHEBANG = "#!python\n"


class PythonPlugin(Plugin):
    """Execute resources starting with `#!python` as Python scripts.

    Such a resource defines a `run(site, resource)` function whose return value
    becomes the resource's content. Generation is done both in `begin_site` (for
    first time) and in `begin_text_resource` (for updates).

    """

    def render(self, resource, text):
        namespace = {}
        exec(text, namespace)
        return namespace["run"](self.site, resource)

    def begin_site(self):
        for node in self.site.content.walk():
            for resource in node.resources:
                source = resource.source_file
                if source.is_binary:
                    continue
                try:
                    with open(source.path, encoding="utf-8") as f:
                        if f.read(len(SHEBANG)) != SHEBANG:
                            continue
                        text = SHEBANG + f.read()
                except UnicodeDecodeError:
                    continue
                target = File(
                    self.site.config.deploy_root_path.child(
                        resource.relative_deploy_path
                    )
                )
                target.parent.make()
                target.write(self.render(resource, text))

    def begin_text_resource(self, resource, text):
        if self.site.config.mode == "production":
            # It was rendered in begin_site
            return
        if not text.startswith(SHEBANG):
            return
        return self.render(resource, text)
