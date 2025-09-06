import sly

from lexer import Lexer

class Parser(sly.Parser):
    tokens = Lexer.tokens
    error = lambda self, token: self.Error(token)

    precedence = (
        ("left", "OR"),
        ("left", "AND"),

        ("left", "BITWISE_OR"),
        ("left", "BITWISE_XOR"),
        ("left", "BITWISE_AND"),

        ("nonassoc", "EQUAL", "NOT_EQUAL", "LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL"),

        ("left", "LSHIFT", "RSHIFT"),

        ("left", "PLUS", "MINUS"),
        ("left", "MUL", "DIV", "MOD"),

        ("right", "NOT", "BITWISE_NOT"),
        ("right", "UMINUS", "REFERENCE", "DEREFERENCE"),

        ("left", "DOT", "ARROW"),
        ("left", "LPAREN", "LBRACKET"),
        ("left", "CAST")
    )

    def __init__(self):
        self.ast = {"type": "module", "body": []}

    def __del__(self):
        self.ast.clear()

    def Parse(self, tokens):
        return self.parse(tokens)

    def Error(self, token):
        assert False, f"Unexpected token in line {token.lineno}: '{token.value}'."

    @_("Statements")
    def Body(self, p):
        self.ast["body"] = p.Statements

    @_("ELSE IF Expr LBRACE Statements RBRACE ElseStatement")
    def ElseStatement(self, p):
        return {"condition": p.Expr, "body": p.Statements, "else": p.ElseStatement}

    @_("ELSE LBRACE Statements RBRACE")
    def ElseStatement(self, p):
        return {"body": p.Statements}

    @_("")
    def ElseStatement(self, p):
        return {"body": []}

    @_("")
    def MemberStatements(self, p):
        return {}

    @_("MemberStatement")
    def MemberStatements(self, p):
        return {p.MemberStatement[1]: p.MemberStatement[0]}

    @_("MemberStatements COMMA MemberStatement")
    def MemberStatements(self, p):
        p.MemberStatements[p.MemberStatement[1]] = p.MemberStatement[0]
        return p.MemberStatements

    @_("PUBLIC TypedName", "PRIVATE TypedName")
    def MemberStatement(self, p):
        return {"value": None, "dataType": p.TypedName[1], "mutable": p.TypedName[2], "private": True if p[0] != "pub" else False}, p.TypedName[0]

    @_("PUBLIC TypedName ASSIGN Expr", "PRIVATE TypedName ASSIGN Expr")
    def MemberStatement(self, p):
        return {"value": p.Expr, "dataType": p.TypedName[1], "mutable": p.TypedName[2], "private": True if p[0] != "pub" else False}, p.TypedName[0]

    @_("")
    def ImplStatements(self, p):
        return []

    @_("ImplStatement")
    def ImplStatements(self, p):
        return [p.ImplStatement]

    @_("ImplStatements ImplStatement")
    def ImplStatements(self, p):
        p.ImplStatements.append(p.ImplStatement)
        return p.ImplStatements

    @_("NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE", "BITWISE_NOT NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "constructor" if p[0] != "~" else "destructor", "body": p.Statements, "params": p.FuncParams}

    @_("NAME LPAREN FuncParams RPAREN SEMICOLON", "BITWISE_NOT NAME LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "constructor" if p[0] != "~" else "destructor", "body": [], "params": p.FuncParams}

    @_("PUBLIC OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE", "PRIVATE OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "operator", "return": p.DataType, "operator": p.FuncOperator, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType SEMICOLON", "PRIVATE OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "operator", "return": p.DataType, "operator": p.FuncOperator, "body": [], "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC OPERATOR FuncOperator LPAREN FuncParams RPAREN LBRACE Statements RBRACE", "PRIVATE OPERATOR FuncOperator LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "operator", "return": "void", "operator": p.FuncOperator, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC OPERATOR FuncOperator LPAREN FuncParams RPAREN SEMICOLON", "PRIVATE OPERATOR FuncOperator LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "operator", "return": "void", "operator": p.FuncOperator, "body": [], "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC NAME LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE", "PRIVATE NAME LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.NAME, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC NAME LPAREN FuncParams RPAREN ARROW DataType SEMICOLON", "PRIVATE NAME LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.NAME, "body": [], "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE", "PRIVATE NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "func", "return": "void", "name": p.NAME, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC NAME LPAREN FuncParams RPAREN SEMICOLON", "PRIVATE NAME LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "func", "return": "void", "name": p.NAME, "body": [], "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("TypedName")
    def TypedNameList(self, p):
        return [p.TypedName]

    @_("TypedNameList COMMA TypedName")
    def TypedNameList(self, p):
        p.TypedNameList.append(p.TypedName)
        return p.TypedNameList

    @_("NAME COLON DataType", "MUT NAME COLON DataType")
    def TypedName(self, p):
        return (p.NAME, p.DataType, p[0] == "mut")

    @_("ArrayName COLON DataType", "MUT ArrayName COLON DataType")
    def TypedName(self, p):
        node = p.ArrayName[0]
        while node["value"]: node = node["value"]
        assert node["value"] is None, "Array is already typed."
        node["value"] = p.DataType
        return (p.ArrayName[1], p.ArrayName[0], p[0] == "mut")

    @_("EnumStatement")
    def EnumStatements(self, p):
        return [p.EnumStatement]
    
    @_("EnumStatements COMMA EnumStatement")
    def EnumStatements(self, p):
        p.EnumStatements.append(p.EnumStatement)
        return p.EnumStatements

    @_("NAME ASSIGN Expr")
    def EnumStatement(self, p):
        return {"name": p.NAME, "value": p.Expr}

    @_("NAME")
    def EnumStatement(self, p):
        return {"name": p.NAME, "value": None}

    @_("Statement")
    def Statements(self, p):
        return [p.Statement]

    @_("Statements Statement")
    def Statements(self, p):
        p.Statements.append(p.Statement)
        return p.Statements

    @_("Expr SEMICOLON")
    def Statement(self, p):
        return p.Expr

    @_("RETURN SEMICOLON")
    def Statement(self, p):
        return {"type": "return", "value": None}

    @_("RETURN Expr SEMICOLON")
    def Statement(self, p):
        return {"type": "return", "value": p.Expr}

    @_("BREAK SEMICOLON", "CONTINUE SEMICOLON")
    def Statement(self, p):
        return {"type": p[0].lower()}

    @_("INCLUDE IncludeParams SEMICOLON")
    def Statement(self, p):
        return {"type": "include", "modules": p.IncludeParams, "namespace": True}

    @_("INCLUDE IncludeParams COLON MUL SEMICOLON")
    def Statement(self, p):
        return {"type": "include", "modules": p.IncludeParams, "namespace": False}

    @_("QualifiedNameTilde LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "func", "return": "void", "name": p.QualifiedNameTilde, "body": p.Statements, "params": p.FuncParams}

    @_("QualifiedNameTilde LPAREN FuncParams RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "func", "return": "void", "name": p.QualifiedNameTilde, "body": [], "params": p.FuncParams}

    @_("FUNC QualifiedName LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.QualifiedName, "body": p.Statements, "params": p.FuncParams}

    @_("FUNC QualifiedName LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def Statement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.QualifiedName, "body": [], "params": p.FuncParams}

    @_("FUNC QualifiedName LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "func", "return": "void", "name": p.QualifiedName, "body": p.Statements, "params": p.FuncParams}

    @_("FUNC QualifiedName LPAREN FuncParams RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "func", "return": "void", "name": p.QualifiedName, "body": [], "params": p.FuncParams}

    @_("IF Expr LBRACE Statements RBRACE ElseStatement")
    def Statement(self, p):
        return {"type": "if", "condition": p.Expr, "body": p.Statements, "else": p.ElseStatement}

    @_("WHILE Expr LBRACE Statements RBRACE ElseStatement")
    def Statement(self, p):
        return {"type": "while", "condition": p.Expr, "body": p.Statements, "else": p.ElseStatement}

    @_("CLASS QualifiedName LBRACE MemberStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "class", "name": p.QualifiedName, "members": p.MemberStatements, "impl": []}

    @_("CLASS QualifiedName LBRACE MemberStatements RBRACE IMPL LBRACE ImplStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "class", "name": p.QualifiedName, "members": p.MemberStatements, "impl": p.ImplStatements}

    @_("CLASS QualifiedName LESS TemplateParams GREATER LBRACE MemberStatements RBRACE IMPL LBRACE ImplStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "template", "body": {"type": "class", "name": p.QualifiedName, "members": p.MemberStatements, "impl": p.ImplStatements}, "params": p.TemplateParams}

    @_("MOD QualifiedName LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "namespace", "name": p.QualifiedName, "body": p.Statements}

    @_("LET LPAREN TypedNameList RPAREN ASSIGN LPAREN ExprList RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "define", "body": [{"type": "define", "name": name, "value": expr, "dataType": type, "mutable": mutable} for (name, type, mutable), expr in zip(p.TypedNameList, p.ExprList)]}

    @_("LET TypedName ASSIGN Expr SEMICOLON")
    def Statement(self, p):
        return {"type": "define", "name": p.TypedName[0], "value": p.Expr, "dataType": p.TypedName[1], "mutable": p.TypedName[2]}

    @_("LET TypedName SEMICOLON")
    def Statement(self, p):
        return {"type": "define", "name": p.TypedName[0], "value": None, "dataType": p.TypedName[1], "mutable": p.TypedName[2]}

    @_("CONST LPAREN TypedNameList RPAREN ASSIGN LPAREN ExprList RPAREN SEMICOLON")
    def Statement(self, p):
        body = []

        for (name, type, mutable), expr in zip(p.TypedNameList, p.ExprList):
            body.append({"type": "define", "name": name, "value": expr, "dataType": type, "mutable": mutable})
            assert not mutable, "Constants must be immutable."

        return {"type": "constant", "body": body}

    @_("CONST TypedName ASSIGN Expr SEMICOLON")
    def Statement(self, p):
        assert not p.TypedName[2], "Constants must be immutable."
        return {"type": "constant", "name": p.TypedName[0], "value": p.Expr, "dataType": p.TypedName[1]}

    @_("TYPE NAME ASSIGN DataType SEMICOLON")
    def Statement(self, p):
        return {"type": "typedef", "name": p.NAME, "value": p.DataType}

    @_("ENUM NAME LBRACE EnumStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "enum", "name": p.NAME, "body": p.EnumStatements, "dataType": None, "class": False}

    @_("ENUM NAME COLON DataType LBRACE EnumStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "enum", "name": p.NAME, "body": p.EnumStatements, "dataType": p.DataType, "class": False}

    @_("ENUM CLASS NAME LBRACE EnumStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "enum", "name": p.NAME, "body": p.EnumStatements, "dataType": None}

    @_("ENUM CLASS NAME COLON DataType LBRACE EnumStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "enum", "name": p.NAME, "body": p.EnumStatements, "dataType": p.DataType}

    @_("EXTERN STRING LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "extern", "linkage": p.STRING[1:-1], "body": p.Statements}

    @_("LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "scope", "body": p.Statements}

    @_("SEMICOLON")
    def Statement(self, p):
        return

    @_("")
    def Statement(self, p):
        return

    @_("NAME")
    def DataType(self, p):
        return p.NAME

    @_("DataType MUL")
    def DataType(self, p):
        return {"type": "pointer", "value": p.DataType}

    @_("DataType LESS TypeParams GREATER")
    def DataType(self, p):
        return {"type": "template", "value": p.DataType, "params": p.TypeParams}

    @_("FUNC LPAREN FuncParams RPAREN ARROW DataType")
    def DataType(self, p):
        return {"type": "function", "return": p.DataType, "params": [i["type"] for i in p.FuncParams]}
    
    @_("FUNC LPAREN FuncParams RPAREN")
    def DataType(self, p):
        return {"type": "function", "return": "void", "params": [i["type"] for i in p.FuncParams]}

    @_("NAME LBRACKET RBRACKET")
    def ArrayName(self, p):
        return {"type": "array", "value": None, "size": None}, p.NAME

    @_("NAME LBRACKET INTEGER RBRACKET")
    def ArrayName(self, p):
        base = 16 if p.INTEGER.startswith("0x") else (8 if p.INTEGER.startswith("0o") else (2 if p.INTEGER.startswith("0b") else 10))
        return {"type": "array", "value": None, "size": int(p.INTEGER.replace("0x", "").replace("0o", "").replace("0b", ""), base)}, p.NAME

    @_("ArrayName LBRACKET RBRACKET")
    def ArrayName(self, p):
        return {"type": "array", "value": p.ArrayName[0], "size": None}, p.ArrayName[1]

    @_("ArrayName LBRACKET INTEGER RBRACKET")
    def ArrayName(self, p):
        base = 16 if p.INTEGER.startswith("0x") else (8 if p.INTEGER.startswith("0o") else (2 if p.INTEGER.startswith("0b") else 10))
        return {"type": "array", "value": p.ArrayName[0], "size": int(p.INTEGER.replace("0x", "").replace("0o", "").replace("0b", ""), base)}, p.ArrayName[1]

    @_("IncludeParams COMMA IncludeParam")
    def IncludeParams(self, p):
        p.IncludeParams.append(p.IncludeParam)
        return p.IncludeParams

    @_("IncludeParam")
    def IncludeParams(self, p):
        return [p.IncludeParam]

    @_("STRING")
    def IncludeParam(self, p):
        return p.STRING[1:-1]

    @_("")
    def FuncParams(self, p):
        return []

    @_("FuncParam")
    def FuncParams(self, p):
        return [p.FuncParam]

    @_("FuncParams COMMA FuncParam")
    def FuncParams(self, p):
        p.FuncParams.append(p.FuncParam)
        return p.FuncParams

    @_("TypedName")
    def FuncParam(self, p):
        return {"name": p.TypedName[0], "type": p.TypedName[1], "mutable": p.TypedName[2]}

    @_("THREE_DOT")
    def FuncParam(self, p):
        return {"type": "three dot"}

    @_("PLUS", "MINUS", "MUL", "DIV", "MOD", "LSHIFT", "RSHIFT", "BITWISE_XOR", "AND", "OR", "BITWISE_AND", "BITWISE_OR", "BITWISE_NOT", "EQUAL", "NOT_EQUAL",
       "GREATER", "LESS", "GREATER_EQUAL", "LESS_EQUAL", "ARROW", "NOT", "ASSIGN", "LPAREN RPAREN", "LBRACKET RBRACKET", "NEW", "DELETE", "COLON COLON", "COMMA",
       "PLUS_ASSIGN", "MINUS_ASSIGN", "MUL_ASSIGN", "DIV_ASSIGN", "MOD_ASSIGN", "LSHIFT_ASSIGN", "RSHIFT_ASSIGN", "XOR_ASSIGN", "AND_ASSIGN", "OR_ASSIGN")
    def FuncOperator(self, p):
        return p[0]

    @_("")
    def CallParams(self, p):
        return []
    
    @_("CallParam")
    def CallParams(self, p):
        return [p.CallParam]
    
    @_("CallParams COMMA CallParam")
    def CallParams(self, p):
        p.CallParams.append(p.CallParam)
        return p.CallParams
    
    @_("Expr")
    def CallParam(self, p):
        return p.Expr
    
    @_("")
    def TypeParams(self, p):
        return []
    
    @_("TypeParam")
    def TypeParams(self, p):
        return [p.TypeParam]
    
    @_("TypeParams COMMA TypeParam")
    def TypeParams(self, p):
        p.TypeParams.append(p.TypeParam)
        return p.TypeParams
    
    @_("DataType")
    def TypeParam(self, p):
        return p.DataType
    
    @_("")
    def TemplateParams(self, p):
        return []
    
    @_("TemplateParam")
    def TemplateParams(self, p):
        return [p.TemplateParam]
    
    @_("TemplateParams COMMA TemplateParam")
    def TemplateParams(self, p):
        p.TemplateParams.append(p.TemplateParam)
        return p.TemplateParams
    
    @_("NAME")
    def TemplateParam(self, p):
        return {"name": p.NAME, "value": None}
    
    @_("NAME ASSIGN Expr")
    def TemplateParam(self, p):
        return {"name": p.NAME, "value": p.Expr}

    @_("")
    def ExprList(self, p):
        return []

    @_("Expr")
    def ExprList(self, p):
        return [p.Expr]

    @_("ExprList COMMA Expr")
    def ExprList(self, p):
        p.ExprList.append(p.Expr)
        return p.ExprList

    @_("LPAREN Expr RPAREN")
    def Expr(self, p):
        return p.Expr

    @_("Expr ASSIGN Expr")
    def Expr(self, p):
        return {"type": "assign", "left": p.Expr0, "right": p.Expr1}

    @_("Expr PLUS_ASSIGN Expr", "Expr MINUS_ASSIGN Expr", "Expr MUL_ASSIGN Expr", "Expr DIV_ASSIGN Expr", "Expr MOD_ASSIGN Expr",
       "Expr LSHIFT_ASSIGN Expr", "Expr RSHIFT_ASSIGN Expr", "Expr XOR_ASSIGN Expr", "Expr AND_ASSIGN Expr", "Expr OR_ASSIGN Expr")
    def Expr(self, p):
        return {"type": "assign", "left": p.Expr0, "right": {"type": "expression", "operator": p[1][0], "left": p.Expr0, "right": p.Expr1}}

    @_("LPAREN ExprList RPAREN ASSIGN LPAREN ExprList RPAREN")
    def Expr(self, p):
        return {"type": "assign", "body": [{"type": "assign", "left": left, "right": right} for left, right in zip(p.ExprList0, p.ExprList1)]}

    @_("QualifiedName")
    def Expr(self, p):
        return {"type": "identifier", "value": p.QualifiedName}

    @_("Expr DOT NAME")
    def Expr(self, p):
        return {"type": "get element", "value": p.Expr, "element": p.NAME}

    @_("Expr ARROW NAME")
    def Expr(self, p):
        return {"type": "get element pointer", "value": p.Expr, "element": p.NAME}

    @_("Expr LPAREN CallParams RPAREN")
    def Expr(self, p):
        return {"type": "call", "value": p.Expr, "params": p.CallParams}

    @_("Expr LBRACKET Expr RBRACKET")
    def Expr(self, p):
        return {"type": "get", "value": p.Expr0, "index": p.Expr1}

    @_("Expr AS DataType %prec CAST")
    def Expr(self, p):
        return {"type": "cast", "value": p.Expr, "target": p.DataType}

    @_("LBRACE ExprList RBRACE")
    def Expr(self, p):
        return {"type": "initializer list", "body": p.ExprList}

    @_("Expr PLUS Expr", "Expr MINUS Expr", "Expr MUL Expr", "Expr DIV Expr", "Expr MOD Expr",  "Expr BITWISE_XOR Expr",
       "Expr LSHIFT Expr", "Expr RSHIFT Expr", "Expr AND Expr", "Expr OR Expr", "Expr BITWISE_AND Expr", "Expr BITWISE_OR Expr",
       "Expr GREATER Expr", "Expr GREATER_EQUAL Expr", "Expr LESS Expr", "Expr LESS_EQUAL Expr", "Expr NOT_EQUAL Expr", "Expr EQUAL Expr")
    def Expr(self, p):
        return {"type": "expression", "operator": p[1], "left": p.Expr0, "right": p.Expr1}

    @_("INTEGER")
    def Expr(self, p):
        type, value = "i32", p.INTEGER

        for signed in ["i", "u"]:
            if signed in value:
                value, bits = p.INTEGER.split(signed)
                assert bits in ["8", "16", "32", "64", "128"], f"Invalid integer bit size: '{bits}'."
                type = f"{signed}{bits}"

        base = 16 if value.startswith("0x") else (8 if value.startswith("0o") else (2 if value.startswith("0b") else 10))
        return {"type": type, "value": int(value[2:] if base != 10 else value, base)}

    @_("FLOAT")
    def Expr(self, p):
        type, value = "f32", p.FLOAT

        if "f" in value:
            value, bits = p.FLOAT.split("f")
            assert bits in ["32", "64"], f"Invalid float bit size: '{bits}'."
            type = f"f{bits}"

        return {"type": type, "value": float(value)}

    @_("STRING")
    def Expr(self, p):
        return {"type": "string", "value": p.STRING[1:-1].replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").replace("\\0", "\0").replace("\\'", "'").replace('\\"', '"')}

    @_("CHAR")
    def Expr(self, p):
        char = p.CHAR[1:-1].replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").replace("\\0", "\0").replace("\\'", "'").replace('\\"', '"')
        assert len(char) == 1, "Expected a single character."
        return {"type": "char", "value": ord(char)}

    @_("TRUE", "FALSE")
    def Expr(self, p):
        return {"type": "bool", "value": 0 if p[0] != "true" else 1}

    @_("NULL")
    def Expr(self, p):
        return {"type": "null"}

    @_("NOT Expr")
    def Expr(self, p):
        return {"type": "not", "value": p.Expr}

    @_("BITWISE_NOT Expr")
    def Expr(self, p):
        return {"type": "bitwise not", "value": p.Expr}

    @_("MINUS Expr %prec UMINUS")
    def Expr(self, p):
        return {"type": "negate", "value": p.Expr}

    @_("BITWISE_AND Expr %prec REFERENCE")
    def Expr(self, p):
        return {"type": "reference", "value": p.Expr}

    @_("MUL Expr %prec DEREFERENCE")
    def Expr(self, p):
        return {"type": "dereference", "value": p.Expr}

    @_("NAME")
    def QualifiedName(self, p):
        return p.NAME

    @_("QualifiedName COLON COLON NAME")
    def QualifiedName(self, p):
        return f"{p.QualifiedName}::{p.NAME}"

    @_("QualifiedName COLON COLON NAME", "QualifiedName COLON COLON BITWISE_NOT NAME")
    def QualifiedNameTilde(self, p):
        return f"{p.QualifiedName}::{"~" if len(p) > 4 else ""}{p.NAME}"