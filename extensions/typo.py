# -*- coding: utf-8 -*-
"""
Plugin to monkey patch typogrify Widont plugin
"""

import unicodedata
import re

# Unicode punctation signs
punct = u''.join(unichr(x) for x in xrange(65536) if unicodedata.category(unichr(x)) == 'Po')

# If we have a space before a punctuation, we need a nbsp for it
def replacer(m):
    if m.group(3) != "":
        return "%s&nbsp;%s&nbsp;%s" % (m.group(1), m.group(2), m.group(4))
    return "%s&nbsp;%s%s" % (m.group(1), m.group(2), m.group(4))

# Monkey patch Typogrify.Widont method
def widont(text):
    # The main modification is that we require a dot at the end of the last word.
    widont_finder = re.compile(r"""((?:</?(?:a|em|span|strong|i|b)[^>]*>)|[^<>\s])
                                       \s+
                                       ([^<>\s]+)(\s*)([""" + punct + """]+
                                       \s*
                                       (</(a|em|span|strong|i|b)>\s*)*
                                       ((</(p|h[1-6]|li|dt|dd)>)|$))
                                       """, re.VERBOSE | re.UNICODE)
    output = widont_finder.sub(replacer, text)
    return output

from typogrify import filters
filters.widont = widont

from hyde.plugin import Plugin

class WidontPlugin(Plugin):
    """Do nothing"""
    pass
