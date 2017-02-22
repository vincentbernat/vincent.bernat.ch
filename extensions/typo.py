# -*- coding: utf-8 -*-
"""
Plugin to handle some typography stuff (monkey-patch typogrify).
"""

import re

from hyde.plugin import Plugin


class FrenchPunctuationPlugin(Plugin):
    """Monkey-patch typogrify to correctly handle french punctuation."""

    NNBSP = u'&#x202f;'

    def __init__(self, site):
        # Patch typogrify
        from typogrify import filters
        original_applyfilters = filters.applyfilters
        filters.applyfilters = lambda text: self.frenchpunct(original_applyfilters(text))

    def frenchpunct(self, text):
        tag_pattern = '</?\w+((\s+\w+(\s*=\s*(?:".*?"|\'.*?\'|[^\'">\s]+))?)+\s*|\s*)/?>'
        space_before_punct_finder = re.compile(r"""(\s|&nbsp;)([:;!\?%»])""", re.UNICODE)
        space_after_punct_finder = re.compile(r"""([«])(\s|&nbsp;)""", re.UNICODE)
        space_between_figures_finder = re.compile(r"""([0-9]|^)(\s|&nbsp;)([0-9]+\W)""", re.UNICODE)
        version_number_finder = re.compile(r"""(\b[A-Z][a-zA-Z]+)(\s|&nbsp;)([0-9]+\W)""", re.UNICODE)
        intra_tag_finder = re.compile(r'(?P<prefix>(%s)?)(?P<text>([^<]*))(?P<suffix>(%s)?)' % (tag_pattern, tag_pattern))

        def _space_process(groups):
            prefix = groups.group('prefix') or ''
            text = groups.group('text')
            text = space_before_punct_finder.sub(self.NNBSP + r"\2", text)
            text = space_after_punct_finder.sub(r"\1" + self.NNBSP, text)
            text = space_between_figures_finder.sub(r"\1" + self.NNBSP + r"\3", text)
            text = version_number_finder.sub(r"\1" + self.NNBSP + r"\3", text)
            suffix = groups.group('suffix') or ''
            return prefix + text + suffix

        output = intra_tag_finder.sub(_space_process, text)
        return output
