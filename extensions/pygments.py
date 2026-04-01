from pygments.lexer import RegexLexer, bygroups, using, include, words
from pygments.token import Text, Comment, Punctuation, Operator, Keyword, Whitespace
from pygments.token import Number, String, Name
from pygments.lexers.go import GoLexer
from pygments.lexers.shell import BashSessionLexer
from pygments.lexers import LEXERS
from hyde.plugin import Plugin

__all__ = ["PigeonLexer", "LezerLexer", "WiresharkLexer", "HurlLexer"]

# To easily test:
"""
python -m pygments -x -f html -Ofull,debug_token_types -l extensions/pygments.py:LezerLexer > ~/tmp/test1.html <<'EOF'
...
EOF
"""


class PygmentPlugin(Plugin):
    def __init__(self, site):
        # Hack to register an internal lexer.
        for lexer in __all__:
            LEXERS[lexer] = (
                "extensions.pygments",
                globals()[lexer].name,
                globals()[lexer].aliases,
                (),
                (),
            )


# It is just good enough to highlight a few excerpts we have!
class PigeonLexer(RegexLexer):
    name = "Pigeon"
    aliases = ["pigeon"]

    tokens = {
        "root": [
            # Comments
            (r"#.*$", Comment.Single),
            (r"//.*$", Comment.Single),
            # Rule operator
            (r"←", Operator),
            # Go blocks
            (r"\{", Punctuation, "go"),
            # Other punctuation
            (r"[()]", Punctuation),
            # Character classes
            (
                r"(\[)([^\]]*(?:\\.[^\]\\]*)*)(\])",
                bygroups(Punctuation, String, Punctuation),
            ),
            # Single and double quoted strings (with optional modifiers)
            (r'("[^"\\]*(?:\\.[^"\\]*)*")(i)?', bygroups(String.Double, Operator)),
            (r"('[^'\\]*(?:\\.[^'\\]*)*')(i)?", bygroups(String.Single, Operator)),
            # Variables
            (r"[a-z]+(?=:)", Name.Variable),
            # Fallback
            (r".", Text),
        ],
        "go": [
            (r"\{", Punctuation, "#push"),
            (r"\}", Punctuation, "#pop"),
            (r"([^{}]|\n)+", using(GoLexer)),
        ],
    }


class LezerLexer(RegexLexer):
    name = "Lezer"
    aliases = ["lezer"]

    tokens = {
        "root": [
            # Comments
            (r"#.*$", Comment.Single),
            (r"//.*$", Comment.Single),
            # Labels
            (r"@[a-z]+", Keyword.Type),
            (r"[a-zA-Z]+(?=\s+\{)", String.Symbol),
            # Character classes
            (
                r"(\[)([^\]]*(?:\\.[^\]\\]*)*)(\])",
                bygroups(Punctuation, String, Punctuation),
            ),
            # Single and double quoted strings (with optional modifiers)
            (r'"[^"\\]*(?:\\.[^"\\]*)*"', String.Double),
            (r"'[^'\\]*(?:\\.[^'\\]*)*'", String.Single),
            # Punctuation
            (r"[\{\}\(\)]", Punctuation),
            # Fallback
            (r".", Text),
        ],
    }


class WiresharkLexer(RegexLexer):
    name = "Wireshark"
    aliases = ["wireshark"]

    tokens = {
        "root": [(r"^\S.+\n", Name.Class, "fields")],
        "fields": [
            # Labels
            (r"^\s+([^:]+)(?=:)", String.Symbol),
            # Numbers
            (
                r"(\()(\d+|0x[a-fA-F0-9]+)(\))",
                bygroups(Punctuation, Number, Punctuation),
            ),
            # Remaining
            (r".|\n", Text),
        ],
    }


class HurlLexer(RegexLexer):
    name = "Hurl"
    aliases = ["hurl"]

    http_methods = (
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "HEAD",
        "OPTIONS",
        "CONNECT",
        "TRACE",
    )
    sections = ("Query", "Cookies", "Captures", "Asserts", "Options")
    asserts = ("variable", "body", "header")

    tokens = {
        "root": [
            # Comments
            (r"#.*$", Comment.Single),
            # HTTP request line
            (
                rf"^({"|".join(http_methods)})(\s+)(\S+)",
                bygroups(Keyword.Reserved, Whitespace, String.Other),
            ),
            # HTTP version and status
            (r"^(HTTP)(\s+)(\d+)", bygroups(Keyword, Whitespace, Number.Integer)),
            # Section markers
            (rf"^\[({"|".join(sections)})\]", Name.Namespace),
            # Key/values
            (
                r"^([A-Za-z0-9\-_]+)(:)(\s*)(.*)",
                bygroups(Name.Attribute, Punctuation, Whitespace, Text),
            ),
            # Asserts
            (
                rf'^({"|".join(asserts)})(\s+)("([^"]+)")',
                bygroups(Keyword, Whitespace, String.Double),
            ),
            # Templates
            (
                r"(\{\{)(\s*)(\w+)(\s*)(\}\})",
                bygroups(
                    Punctuation, Whitespace, Name.Variable, Whitespace, Punctuation
                ),
            ),
            # Remaining
            (r"[><=!]+", Operator),
            (r"\b\d+\b", Number.Integer),
            (r"\s+", Whitespace),
            (r".", Text),
        ],
    }


# Patch BashSessionLexer
BashSessionLexer._bare_continuation = True
