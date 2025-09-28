import sly

def group(*choices): return rf"({'|'.join(choices)})"
def any(*choices): return group(*choices) + r"*"
def maybe(*choices): return group(*choices) + r"?"

IntegerSuffix = maybe(*[rf"{signed}{bits}" for signed in [r"i", r"u"] for bits in [8, 16, 32, 64, 128]])
HexInteger = r"0[xX][0-9a-fA-F]+" + IntegerSuffix
BinInteger = r"0[bB][01]+" + IntegerSuffix
OctInteger = r"0[oO][0-7]+" + IntegerSuffix
DecInteger = r"[0-9]+" + IntegerSuffix

FloatSuffix = maybe(*[rf"f{bits}" for bits in [32, 64]])
Exponent = r"[eE][-+]?[0-9]*"
PointFloat = group(r"[0-9]+\.[0-9]*", r"[0-9]*\.[0-9]+") + maybe(Exponent) + FloatSuffix
ExpFloat = r"[0-9]+" + Exponent + FloatSuffix

class Lexer(sly.Lexer):
    tokens = {
        THREE_DOT, FLOAT, INTEGER, STRING, CHAR, NAME,

        IF, ELSE, FOR, WHILE, FUNC, CLASS, RETURN, BREAK, CONTINUE, CONST, OPERATOR, PUBLIC, PRIVATE,
        INCLUDE, USE, MOD, TYPE, LET, MUT, TRUE, FALSE, NULL, IMPL, NEW, DEL, EXTERN, ENUM, AS,

        PLUS_ASSIGN, MINUS_ASSIGN, MUL_ASSIGN, DIV_ASSIGN, MOD_ASSIGN, LSHIFT_ASSIGN, RSHIFT_ASSIGN, AND_ASSIGN, OR_ASSIGN, XOR_ASSIGN,

        QUESTION_MARK, AND, BITWISE_AND, OR, BITWISE_OR, BITWISE_XOR, EQUAL, NOT_EQUAL, ARROW, GREATER_EQUAL, LESS_EQUAL, GREATER, LESS, ASSIGN, LBRACKET,
        RBRACKET, LBRACE, RBRACE, LPAREN, RPAREN, PLUS, MINUS, COMMA, MUL, DIV, BACKSLASH, MOD, DOUBLE_COLON, COLON, SEMICOLON, NOT, BITWISE_NOT, DOT
    }

    def __init__(self):
        ...

    def __del__(self):
        ...

    def Lex(self, text):
        return self.tokenize(text)

    def Error(self, token):
        assert False, f"Invalid character in line {self.lineno}: '{token.value[0]}'."

    @_(r"\n")
    def NewLine(self, token):
        self.lineno += 1

    @_(r"//.*", r"/\*[\s\S]*?\*/")
    def Comment(self, token):
        ...
    
    THREE_DOT = r"\.\.\."
    FLOAT = group(PointFloat, ExpFloat)
    INTEGER = group(HexInteger, BinInteger, OctInteger, DecInteger)
    STRING, CHAR = r'"(\\.|[^"\\])*"', r"'(\\.|[^'\\])'"

    ignore = "".join(["\t", "\r", " "])
    error = lambda self, token: self.Error(token)

    NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"

    NAME["if"] = IF
    NAME["else"] = ELSE
    NAME["for"] = FOR
    NAME["while"] = WHILE
    NAME["func"] = FUNC
    NAME["class"] = CLASS
    NAME["ret"] = RETURN
    NAME["break"] = BREAK
    NAME["continue"] = CONTINUE
    NAME["const"] = CONST
    NAME["op"] = OPERATOR
    NAME["pub"] = PUBLIC
    NAME["priv"] = PRIVATE
    NAME["include"] = INCLUDE
    NAME["use"] = USE
    NAME["mod"] = MOD
    NAME["type"] = TYPE
    NAME["let"] = LET
    NAME["mut"] = MUT
    NAME["true"] = TRUE
    NAME["false"] = FALSE
    NAME["null"] = NULL
    NAME["impl"] = IMPL
    NAME["new"] = NEW
    NAME["del"] = DEL
    NAME["extern"] = EXTERN
    NAME["enum"] = ENUM
    NAME["as"] = AS

    PLUS_ASSIGN = r"\+="
    MINUS_ASSIGN = r"-="
    MUL_ASSIGN = r"\*="
    DIV_ASSIGN = r"/="
    MOD_ASSIGN = r"%="
    LSHIFT_ASSIGN = r"<<="
    RSHIFT_ASSIGN = r">>="
    AND_ASSIGN = r"&="
    OR_ASSIGN = r"\|="
    XOR_ASSIGN = r"\^="

    AND, BITWISE_AND = r"\&\&", r"\&"
    OR, BITWISE_OR, BITWISE_XOR = r"\|\|", r"\|", r"\^"
    EQUAL, NOT_EQUAL, ARROW = r"==", r"!=", r"->"
    GREATER_EQUAL, LESS_EQUAL = r">=", r"<="
    GREATER, LESS, ASSIGN = r">", r"<", r"="
    LBRACKET, RBRACKET = r"\[", r"\]"
    LBRACE, RBRACE = r"\{", r"\}"
    LPAREN, RPAREN = r"\(", r"\)"
    PLUS, MINUS, COMMA = r"\+", r"-", r","
    MUL, DIV, BACKSLASH = r"\*", r"/", r"\\"
    DOUBLE_COLON, COLON = r"::", r":"
    MOD, SEMICOLON, NOT = r"%", r";", r"!"
    BITWISE_NOT, DOT = r"~", r"\."
    QUESTION_MARK = r"\?"