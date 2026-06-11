from hyde.plugin import Plugin
from fswrap import File

SHEBANG = "#!python\n"


class PythonPlugin(Plugin):
    """Execute resources starting with `#!python` as Python scripts.

    Such a resource defines a `run(site, resource)` function whose return value
    becomes the resource's content.

    """

    @staticmethod
    def render(site, resource, text):
        """Execute a `#!python` resource and return its content."""
        namespace = {}
        exec(text, namespace)
        return namespace["run"](site, resource)

    @classmethod
    def ensure_generated(cls, resource):
        """Render a `#!python` resource to its deploy path if missing or outdated.

        Consumers that read a resource's deployed file directly (e.g. cover
        images) may run before that resource has been generated; this
        materializes it on demand.

        """
        source = resource.source_file
        if source.is_binary:
            return
        try:
            text = source.read_all()
        except UnicodeDecodeError:
            return
        if not text.startswith(SHEBANG):
            return
        target = File(
            resource.site.config.deploy_root_path.child(resource.relative_deploy_path)
        )
        if target.exists and not target.older_than(source):
            return
        target.parent.make()
        target.write(cls.render(resource.site, resource, text))

    def begin_text_resource(self, resource, text):
        if not text.startswith(SHEBANG):
            return
        return self.render(self.site, resource, text)
