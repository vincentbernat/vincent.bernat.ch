"""
CSS plugins
"""

import os
import struct
import subprocess
import xml.etree.ElementTree as ET
from hyde.plugin import Plugin


def font_baseline_offset(font_path):
    """Compute baseline position as (ascent - descent) / (2 * upm) from OS/2 table."""
    xml = subprocess.check_output(
        ["ttx", "-t", "OS/2", "-t", "head", "-o", "/dev/stdout", font_path],
        stderr=subprocess.DEVNULL,
    )
    root = ET.fromstring(xml)
    upm = int(root.find(".//head/unitsPerEm").get("value"))
    ascent = int(root.find(".//OS_2/sTypoAscender").get("value"))
    descent = abs(int(root.find(".//OS_2/sTypoDescender").get("value")))
    return (ascent - descent) / (2 * upm)


class PostCSSPlugin(Plugin):
    """Run PostCSS on CSS files."""

    def begin_site(self):
        depends = ["media/css/root.css", "media/css/common.css"]
        for resource in self.site.content.walk_resources():
            if resource.source_file.kind == "css":
                if resource.relative_path in depends:
                    continue
                if not hasattr(resource, "depends") or not resource.depends:
                    resource.depends = []
                resource.depends.extend(depends)
                resource.depends = list(set(resource.depends))

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "css":
            return
        font_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "content",
            "media",
            "fonts",
            "merriweather.woff2",
        )
        env = os.environ.copy()
        env["CSS_MINIFY"] = (
            "false" if self.site.config.mode == "development" else "true"
        )
        env["CSS_BASELINE_OFFSET"] = str(font_baseline_offset(font_path))
        script = os.path.join(os.path.dirname(__file__), "css.js")
        p = subprocess.Popen(
            ["node", script, "process"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
        )
        stdout, _ = p.communicate(text.encode("utf-8"))
        assert p.returncode == 0, f"error while processing CSS resource {resource}"
        return stdout.decode("utf-8")
