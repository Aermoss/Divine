import sys, sly

def group(*choices): return rf"({'|'.join(choices)})"
def any(*choices): return group(*choices) + r"*"
def maybe(*choices): return group(*choices) + r"?"

HexInteger = r"0[xX][0-9a-fA-F]+"
BinInteger = r"0[bB][01]+"
OctInteger = r"0[oO][0-7]+"
DecInteger = r"[0-9]+"
Exponent = r"[eE][-+]?[0-9]*"
PointFloat = group(r"[0-9]+\.[0-9]*", r"[0-9]*\.[0-9]+") + maybe(Exponent) + r"[fF]?"
ExpFloat = r"[0-9]+" + Exponent + r"[fF]?"

class Lexer(sly.Lexer):
    tokens = {
        FLOAT, INTEGER, STRING, CHAR, NAME, IF, ELSE, FOR, DO, WHILE, FUNC, CLASS, RETURN, BREAK, CONTINUE, PUBLIC, PRIVATE, INCLUDE, USE, MOD, TYPE, NEW, DELETE, OPERATOR,
        CONST, DEST, LET, LSHIFT, RSHIFT, NOT, BITWISE_NOT, AND, BITWISE_AND, OR, BITWISE_OR, XOR, COMMA, EQUALS, EQUAL, NOT_EQUAL, GREATER_EQUAL, LESS_EQUAL, LBRACKET, RBRACKET, QUESTION_MARK,
        ARROW, GREATER, LESS, LBRACE, RBRACE, LPAREN, RPAREN, PLUS, MINUS, ASTERISK, SLASH, BACKSLASH, MOD, COLON, SEMICOLON, THREE_DOT, DOT, TRUE, FALSE, NULL, IMPL
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
    STRING, CHAR = r"\".*?\"", r"\'(\\)?.\'"

    ignore = "".join(["\t", "\r", " "])
    error = lambda self, token: self.Error(token)

    NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"

    NAME["if"] = IF
    NAME["else"] = ELSE
    NAME["for"] = FOR
    NAME["do"] = DO
    NAME["while"] = WHILE
    NAME["func"] = FUNC
    NAME["class"] = CLASS
    NAME["ret"] = RETURN
    NAME["break"] = BREAK
    NAME["continue"] = CONTINUE
    NAME["operator"] = OPERATOR
    NAME["pub"] = PUBLIC
    NAME["priv"] = PRIVATE
    NAME["include"] = INCLUDE
    NAME["use"] = USE
    NAME["mod"] = MOD
    NAME["type"] = TYPE
    NAME["const"] = CONST
    NAME["dest"] = DEST
    NAME["let"] = LET
    NAME["true"] = TRUE
    NAME["false"] = FALSE
    NAME["null"] = NULL
    NAME["impl"] = IMPL
    NAME["new"] = NEW
    NAME["delete"] = DELETE

    LSHIFT, RSHIFT = r"<<", r">>"
    AND, BITWISE_AND = r"\&\&", r"\&"
    OR, BITWISE_OR, XOR = r"\|\|", r"\|", r"\^"
    EQUAL, NOT_EQUAL, ARROW = r"==", r"!=", r"->"
    GREATER_EQUAL, LESS_EQUAL = r">=", r"<="
    GREATER, LESS, EQUALS = r">", r"<", r"="
    LBRACKET, RBRACKET = r"\[", r"\]"
    LBRACE, RBRACE = r"\{", r"\}"
    LPAREN, RPAREN = r"\(", r"\)"
    PLUS, MINUS, COMMA = r"\+", r"-", r","
    ASTERISK, SLASH, BACKSLASH = r"\*", r"/", r"\\"
    MOD, COLON, SEMICOLON = r"%", r":", r";"
    NOT, BITWISE_NOT, DOT = r"!", r"~", r"\."
    QUESTION_MARK = r"\?"