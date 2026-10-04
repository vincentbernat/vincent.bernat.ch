from pygments.lexer import RegexLexer, bygroups, using
from pygments.token import Text, Comment, Punctuation, Operator, Keyword, Whitespace
from pygments.token import Number, String, Name
from pygments.lexers.go import GoLexer
from pygments.lexers.shell import BashSessionLexer
from pygments.lexers import LEXERS
from hyde.plugin import Plugin

__all__ = [
    "PigeonLexer",
    "LezerLexer",
    "WiresharkLexer",
    "HurlLexer",
    "SshConfigLexer",
    "GoAsmLexer",
    "GoAstLexer",
    "GoSsaLexer",
    "GoRulesLexer",
]

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
        "root": [
            # Protocol names are not indented
            (r"^\S.*$", Name.Class),
            # [Time shift for this packet: 0.0 seconds]
            (r"^\s*(\[[^\]]+\])$", Comment),
            # "    .... ..0. .... .... = LG bit: value"
            (
                r"^(\s+)([.01 ]+)(= )([^:]+)(?=:)",
                bygroups(Text, Name.Constant, Operator, String.Symbol),
            ),
            # Labels
            (r"^[^\S\n]+([^:\n]+)(?=:)", String.Symbol),
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


class GoAsmLexer(RegexLexer):
    name = "Go assembly"
    aliases = ["goasm", "go-asm"]

    pseudo_instructions = (
        "TEXT",
        "DATA",
        "GLOBL",
        "FUNCDATA",
        "PCDATA",
        "PCALIGN",
    )
    symbol_attributes = (
        "ABIInternal",
        "ABI0",
        "DUPOK",
        "LOCAL",
        "NEEDCTXT",
        "NOFRAME",
        "NOPROF",
        "NOPTR",
        "NOSPLIT",
        "REFLECTMETHOD",
        "RODATA",
        "TLSBSS",
        "TOPFRAME",
        "WRAPPER",
    )
    # Hardware and pseudo registers, for all the architectures Go supports
    registers = (
        r"[ABCD][XLH]|[SD]IL?|BPL?|SPL?|R\d{1,2}[BWDL]?|[BDFHKMQSVXYZ]\d{1,2}"
        r"|RSP|ZR|ZERO|LR|CTR|XER|SB|FP|PC|g"
    )

    tokens = {
        "root": [
            # Comments. Semicolon is a statement separator in real Go
            # assembly, but our listings use it to annotate instructions.
            (r"(//|;).*$", Comment.Single),
            (r"/\*", Comment.Multiline, "comment"),
            # Labels
            (
                r"^([^\S\n]*)([\w.·]+)(:)",
                bygroups(Whitespace, Name.Label, Punctuation),
            ),
            # Pseudo instructions
            (
                rf"^([^\S\n]*)({"|".join(pseudo_instructions)})\b",
                bygroups(Whitespace, Keyword.Declaration),
            ),
            # Instructions
            (
                r"^([^\S\n]*)([A-Z][A-Z0-9]*(?:\.[A-Z]+)*)\b",
                bygroups(Whitespace, Name.Function),
            ),
            # Attributes of a TEXT or GLOBL symbol
            (rf"\b(?:{"|".join(symbol_attributes)})\b", Keyword),
            # Registers
            (rf"\b(?:{registers})\b", Name.Variable),
            # Constants
            (r"\$", Operator),
            (r"-?0[xX][0-9a-fA-F]+", Number.Hex),
            (r"-?\d+", Number.Integer),
            (r'"(?:\\.|[^"\\])*"', String.Double),
            # Symbols, with the package path and the middle dot Go uses
            (r"[\w·][\w.·∕/$\[\]=]*", String.Symbol),
            # Remaining
            (r"[-+*|&^~<>]+", Operator),
            (r"[(),]", Punctuation),
            (r"[^\S\n]+", Whitespace),
            (r".|\n", Text),
        ],
        "comment": [
            (r"[^*]+", Comment.Multiline),
            (r"\*/", Comment.Multiline, "#pop"),
            (r"\*", Comment.Multiline),
        ],
    }


class GoAstLexer(RegexLexer):
    name = "Go compiler IR"
    aliases = ["go-ast", "go-ir"]

    tokens = {
        "root": [
            # Source position
            (r"#.*$", Comment.Single),
            # Depth, operation and optional field name (IF-Cond)
            (
                r"^((?:\.[^\S\n]*)*)([A-Z][A-Z0-9]*(?:-[A-Za-z]\w*$)?)",
                bygroups(Whitespace, Keyword),
            ),
            # Kind of a type (FUNC-func(), ARRAY-[16]byte)
            (r"\b([A-Z]+)(-)", bygroups(Keyword.Type, Punctuation)),
            # Attributes (Class:PPARAM, tc(1), OnStack)
            (r"\b(\w+)(:)(\w+)", bygroups(Name.Attribute, Punctuation, Name.Constant)),
            (r"\btc\(\d+\)", Name.Attribute),
            (r"\w+\.[\w.~]+", Text),
            (r"\b[A-Z][a-zA-Z]+\b", Name.Attribute),
            # Remaining
            (r"\d+", Number.Integer),
            (r"\w+", Text),
            (r"-", Punctuation),
            (r"[^\S\n]+", Whitespace),
            (r".|\n", Text),
        ],
    }


class GoSsaLexer(RegexLexer):
    name = "Go compiler SSA"
    aliases = ["go-ssa"]

    tokens = {
        "root": [
            (r";.*$", Comment.Single),
            # Source position ((+12), (-11), (?))
            (r"^([^\S\n]*)(\([+-]?\d+\)|\(\?\))", bygroups(Whitespace, Whitespace)),
            # Block label and block kind (If, Plain, Ret)
            (r"^([^\S\n]*)(b\d+)(:)", bygroups(Whitespace, Name.Label, Punctuation)),
            (
                r"^([^\S\n]*)(If|Plain|Ret|RetJmp|Exit|First|Defer|JumpTable)\b",
                bygroups(Whitespace, Keyword),
            ),
            # Value and its operation
            (
                r"(v\d+)([^\S\n]*)(=)([^\S\n]*)([A-Z]\w*)",
                bygroups(Name.Variable, Whitespace, Operator, Whitespace, Keyword),
            ),
            # Type, aux value and aux integer
            (r"<[^>\n]*>", Keyword.Type),
            (r"\{[^}\n]*\}", Name.Attribute),
            (r"\[[^\]\n]*\]", Number.Integer),
            # Names of the value, at the end of the line
            (r"\([^)\n]*\)(?=[^\S\n]*(;|$))", Whitespace),
            # References
            (r"\bv\d+\b", Name.Variable),
            (r"\bb\d+\b", Name.Label),
            (r"<-|->", Operator),
            # Remaining
            (r"\w+", Text),
            (r"[^\S\n]+", Whitespace),
            (r".|\n", Text),
        ],
    }


class GoRulesLexer(RegexLexer):
    name = "Go compiler SSA rules"
    aliases = ["go-rules"]

    tokens = {
        "root": [
            (r"//.*$", Comment.Single),
            # Operation after a parenthesis (Load, BSWAP(Q|L))
            (
                r"(\()([A-Z]\w*(?:\([\w|]+\)\w*)*)",
                bygroups(Punctuation, Keyword),
            ),
            # Type, aux value and aux integer, like in SSA
            (r"<[\w.*\[\]]+>", Keyword.Type),
            (r"\{[^}\n]*\}", Name.Attribute),
            (r"\[[^\]\n]*\]", Number.Integer),
            # Block where to put the result
            (r"@[\w.]+", Name.Decorator),
            # Functions in conditions
            (r"[\w.]+(?=\()", Name.Function),
            # Remaining
            (r"=>|&&|\|\||[!<>=]=?|[-+*]", Operator),
            (r"\d+", Number.Integer),
            (r"\w+", Text),
            (r"[()]", Punctuation),
            (r"\s+", Whitespace),
            (r".", Text),
        ],
    }


class SshConfigLexer(RegexLexer):
    name = "SSH config"
    aliases = ["ssh-config", "sshd-config"]

    tokens = {
        "root": [
            # Comments
            (r"#.*$", Comment.Single),
            # Directives opening a block
            (r"^([^\S\n]*)(Host|Match)\b", bygroups(Whitespace, Keyword)),
            # Any other word starting a line is a directive
            (r"^([^\S\n]*)(\w+)", bygroups(Whitespace, Name.Attribute)),
            # Values
            (r'"[^"]*"', String.Double),
            (r"\b(yes|no)\b", Keyword.Constant),
            (r"(?<![\w.])\d+(?![\w.])", Number.Integer),
            (r"[=,]", Punctuation),
            # Remaining
            (r"[^\S\n]+", Whitespace),
            (r"\n", Whitespace),
            (r".", Text),
        ],
    }


# Patch BashSessionLexer
BashSessionLexer._bare_continuation = True
