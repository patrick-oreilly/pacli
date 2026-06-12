from pygments.style import Style
from pygments.token import (
    Token,
    Whitespace,
    Error,
    Other,
    Comment,
    Keyword,
    Operator,
    Punctuation,
    Name,
    Number,
    Literal,
    String,
    Generic,
)


class IcySyntaxStyle(Style):
    """Muted icy-tones syntax theme for pacli code blocks.

    Restricted palette: soft purples, pale blues, dim greens, stark whites.
    Key identifiers and function names pop in electric cyan (#00F0FF).
    No full ANSI rainbow.
    """

    name = "icy"
    background_color = "#0D0D14"
    highlight_color = "#1A1A2E"

    styles = {
        Token:                     "#E8E8F0",  # stark white (default text)
        Whitespace:                "",
        Error:                     "#E06C75",
        Other:                     "",

        # Comments: dim green
        Comment:                   "#7DA87D",
        Comment.Multiline:         "",
        Comment.Preproc:           "#9ACD9A",
        Comment.Single:            "",
        Comment.Special:           "",

        # Keywords: soft purple
        Keyword:                   "#B0A0D8",
        Keyword.Constant:          "",
        Keyword.Declaration:       "",
        Keyword.Namespace:         "#C0B0E8",
        Keyword.Pseudo:            "",
        Keyword.Reserved:          "",
        Keyword.Type:              "",

        # Operators: dim white
        Operator:                  "#C8C8D8",
        Operator.Word:             "",

        # Punctuation: dim white
        Punctuation:               "#C8C8D8",

        # Names/Identifiers
        Name:                      "#E8E8F0",
        Name.Attribute:            "#00F0FF",  # electric cyan
        Name.Builtin:              "#00F0FF",
        Name.Builtin.Pseudo:       "",
        Name.Class:                "#00F0FF",
        Name.Constant:             "#00F0FF",
        Name.Decorator:            "#B0A0D8",
        Name.Entity:               "#00F0FF",
        Name.Exception:            "#00F0FF",
        Name.Function:             "#00F0FF",
        Name.Property:             "#E8E8F0",
        Name.Label:                "",
        Name.Namespace:            "#E8E8F0",
        Name.Other:                "#E8E8F0",
        Name.Tag:                  "#B0A0D8",
        Name.Variable:             "#E8E8F0",
        Name.Variable.Class:       "#00F0FF",
        Name.Variable.Global:      "#E8E8F0",
        Name.Variable.Instance:    "#E8E8F0",

        # Numbers: muted warm
        Number:                    "#D0C0B0",
        Number.Float:              "",
        Number.Hex:                "",
        Number.Integer:            "",
        Number.Integer.Long:       "",
        Number.Oct:                "",

        # Literals
        Literal:                   "#D0C0B0",
        Literal.Date:              "#90CAF9",

        # Strings: pale blue
        String:                    "#90CAF9",
        String.Backtick:           "",
        String.Char:               "#90CAF9",
        String.Doc:                "#7DA87D",
        String.Double:             "",
        String.Escape:             "#B0A0D8",
        String.Heredoc:            "",
        String.Interpol:           "#00F0FF",
        String.Other:              "",
        String.Regex:              "#90CAF9",
        String.Single:             "",
        String.Symbol:             "",

        # Generic
        Generic:                   "",
        Generic.Deleted:           "",
        Generic.Emph:              "",
        Generic.Error:             "",
        Generic.Heading:           "",
        Generic.Inserted:          "",
        Generic.Output:            "#90CAF9",
        Generic.Prompt:            "",
        Generic.Strong:            "",
        Generic.EmphStrong:        "",
        Generic.Subheading:        "#7DA87D",
        Generic.Traceback:         "",
    }
