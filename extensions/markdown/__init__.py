# Patch ReferencePattern to handle additional spaces at the beginning
# of a line
from markdown import inlinepatterns
import re

inlinepatterns.ReferencePattern.NEWLINE_CLEANUP_RE = re.compile(r"\s+", re.MULTILINE)

# Accept "details" as a block element
from markdown import util


def _isBlockLevel(tag):
    if isinstance(tag, util.string_type):
        return util.BLOCK_LEVEL_ELEMENTS.match(tag) or tag == "details"
    return False


util.isBlockLevel = _isBlockLevel
