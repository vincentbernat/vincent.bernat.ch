# Patch ReferencePattern to handle additional spaces at the beginning
# of a line
from markdown import inlinepatterns
import re
inlinepatterns.ReferencePattern.NEWLINE_CLEANUP_RE = re.compile(r'\s+', re.MULTILINE)
