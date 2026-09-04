"""
JavaScript plugins
"""

from hyde.plugin import CLTransformer
from fswrap import File


class EsbuildPlugin(CLTransformer):
    """
    esbuild plugin
    """

    @property
    def executable_name(self):
        return "esbuild"

    @property
    def plugin_name(self):
        return "esbuild"

    def text_resource_complete(self, resource, text):
        mode = self.site.config.mode
        if resource.source_file.kind != "js":
            return

        esbuild = self.app
        source = File.make_temp(text)
        target = File.make_temp("")
        args = [
            str(esbuild),
            str(source),
            "--target=es2015",
            f"--outfile={target}",
            "--log-level=warning",
        ]
        if mode == "production":
            args.append("--minify")
        self.call_app(args)
        return target.read_all()
