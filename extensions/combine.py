"""
Modified combine plugin.

This plugin is like the `combine` plugin except it combines resources
in the "complete" step.
"""

from hyde.ext.plugins.structure import CombinePlugin as OrigCombinePlugin


class CombinePlugin(OrigCombinePlugin):
    def text_resource_complete(self, resource, text):
        return super().begin_text_resource(resource, text)

    def begin_text_resource(self, resource, text):
        pass
