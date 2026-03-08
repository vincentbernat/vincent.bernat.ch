"""
CSS plugins
"""

import os
import subprocess
from hyde.plugin import Plugin


class CSSPrefixerPlugin(Plugin):
    """Run CSS prefixer"""

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "css":
            return
        env = os.environ.copy()
        env["CSS_MINIFY"] = (
            "false" if self.site.config.mode == "development" else "true"
        )
        script = os.path.join(os.path.dirname(__file__), "css.js")
        p = subprocess.Popen(
            ["node", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
        )
        stdout, _ = p.communicate(text.encode("utf-8"))
        assert p.returncode == 0
        return stdout.decode("utf-8")
