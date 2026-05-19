"""
SVG plugins
"""

import os
import subprocess
from hyde.plugin import Plugin


class SVGOPlugin(Plugin):
    """Run SVGO on SVG files."""

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "svg":
            return
        script = os.path.join(os.path.dirname(__file__), "svg.js")
        p = subprocess.Popen(
            ["node", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        stdout, _ = p.communicate(text.encode("utf-8"))
        assert p.returncode == 0, f"error while processing SVG resource {resource}"
        return stdout.decode("utf-8")
