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

        ("left", "CAST"),
        ("right", "TERNARY"),

        ("left", "LSHIFT", "RSHIFT"),

        ("left", "PLUS", "MINUS"),
        ("left", "MUL", "DIV", "MOD"),

        ("right", "NOT", "BITWISE_NOT"),
        ("right", "UNARY_MINUS", "ADDRESS_OF", "DEREFERENCE"),

        ("left", "DOT", "ARROW"),
        ("left", "LPAREN", "LBRACKET")
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

    @_("ELSE IF Expr LBRACE Statements RBRACE")
    def ElseStatement(self, p):
        return {"condition": p.Expr, "body": p.Statements}

    @_("ELSE IF Expr LBRACE Statements RBRACE ElseStatement")
    def ElseStatement(self, p):
        return {"condition": p.Expr, "body": p.Statements, "else": p.ElseStatement}

    @_("ELSE LBRACE Statements RBRACE")
    def ElseStatement(self, p):
        return {"body": p.Statements}

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
        assert not p.TypedName[2], "Class members are mutable by default."
        return {"value": None, "dataType": p.TypedName[1], "private": True if p[0] != "pub" else False}, p.TypedName[0]

    @_("PUBLIC TypedName ASSIGN Expr", "PRIVATE TypedName ASSIGN Expr")
    def MemberStatement(self, p):
        assert not p.TypedName[2], "Class members are mutable by default."
        return {"value": p.Expr, "dataType": p.TypedName[1], "private": True if p[0] != "pub" else False}, p.TypedName[0]

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

    @_("Constructor")
    def ConstructorList(self, p):
        return [p.Constructor]
    
    @_("ConstructorList COMMA Constructor")
    def ConstructorList(self, p):
        for constructor in p.ConstructorList:
            assert constructor["class"] != p.Constructor["class"], f"Constructor for '{constructor['class']}' is already called."

        p.ConstructorList.append(p.Constructor)
        return p.ConstructorList

    @_("DataType LPAREN ExprList RPAREN")
    def Constructor(self, p):
        return {"type": "constructor", "class": p.DataType, "params": p.ExprList}

    @_("NAME LPAREN FuncParams RPAREN COLON ConstructorList LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "constructor", "body": p.Statements, "params": p.FuncParams, "constructors": p.ConstructorList}

    @_("NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE", "BITWISE_NOT NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "constructor" if p[0] != "~" else "destructor", "body": p.Statements, "params": p.FuncParams}

    @_("NAME LPAREN FuncParams RPAREN SEMICOLON", "BITWISE_NOT NAME LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "constructor" if p[0] != "~" else "destructor", "params": p.FuncParams}

    @_("PUBLIC OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE", "PRIVATE OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "operator", "return": p.DataType, "operator": p.FuncOperator, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType SEMICOLON", "PRIVATE OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "operator", "return": p.DataType, "operator": p.FuncOperator, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC OPERATOR FuncOperator LPAREN FuncParams RPAREN LBRACE Statements RBRACE", "PRIVATE OPERATOR FuncOperator LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "operator", "return": "void", "operator": p.FuncOperator, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC OPERATOR FuncOperator LPAREN FuncParams RPAREN SEMICOLON", "PRIVATE OPERATOR FuncOperator LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "operator", "return": "void", "operator": p.FuncOperator, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC NAME LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE", "PRIVATE NAME LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.NAME, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC NAME LPAREN FuncParams RPAREN ARROW DataType SEMICOLON", "PRIVATE NAME LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.NAME, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE", "PRIVATE NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "func", "return": "void", "name": p.NAME, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC NAME LPAREN FuncParams RPAREN SEMICOLON", "PRIVATE NAME LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "func", "return": "void", "name": p.NAME, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

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

    @_("")
    def Statements(self, p):
        return []

    @_("Statement")
    def Statements(self, p):
        return [p.Statement]

    @_("Statements Statement")
    def Statements(self, p):
        p.Statements.append(p.Statement)
        return p.Statements

    @_("RETURN SEMICOLON")
    def Statement(self, p):
        return {"type": "return", "value": None}

    @_("RETURN Expr SEMICOLON")
    def Statement(self, p):
        return {"type": "return", "value": p.Expr}

    @_("BREAK SEMICOLON", "CONTINUE SEMICOLON")
    def Statement(self, p):
        return {"type": p[0].lower()}

    @_("INCLUDE IncludeParams COLON MUL SEMICOLON")
    def Statement(self, p):
        return {"type": "include", "modules": p.IncludeParams}

    @_("FUNC NAME LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.NAME, "body": p.Statements, "params": p.FuncParams}

    @_("FUNC NAME LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def Statement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.NAME, "params": p.FuncParams}

    @_("FUNC NAME LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "func", "return": "void", "name": p.NAME, "body": p.Statements, "params": p.FuncParams}

    @_("FUNC NAME LPAREN FuncParams RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "func", "return": "void", "name": p.NAME, "params": p.FuncParams}

    @_("IF Expr LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "if", "condition": p.Expr, "body": p.Statements}

    @_("IF Expr LBRACE Statements RBRACE ElseStatement")
    def Statement(self, p):
        return {"type": "if", "condition": p.Expr, "body": p.Statements, "else": p.ElseStatement}

    @_("WHILE Expr LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "while", "condition": p.Expr, "body": p.Statements}

    @_("CLASS NAME LBRACE MemberStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "class", "name": p.NAME, "members": p.MemberStatements, "impl": [], "parents": []}

    @_("CLASS NAME LBRACE MemberStatements RBRACE IMPL LBRACE ImplStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "class", "name": p.NAME, "members": p.MemberStatements, "impl": p.ImplStatements, "parents": []}

    @_("CLASS NAME LESS TemplateParams GREATER LBRACE MemberStatements RBRACE IMPL LBRACE ImplStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "template", "body": {"type": "class", "name": p.NAME, "members": p.MemberStatements, "impl": p.ImplStatements, "parents": []}, "params": p.TemplateParams}

    @_("CLASS NAME COLON TypeList LBRACE MemberStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "class", "name": p.NAME, "members": p.MemberStatements, "impl": [], "parents": p.TypeList}

    @_("CLASS NAME COLON TypeList LBRACE MemberStatements RBRACE IMPL LBRACE ImplStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "class", "name": p.NAME, "members": p.MemberStatements, "impl": p.ImplStatements, "parents": p.TypeList}

    @_("CLASS NAME COLON TypeList LESS TemplateParams GREATER LBRACE MemberStatements RBRACE IMPL LBRACE ImplStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "template", "body": {"type": "class", "name": p.NAME, "members": p.MemberStatements, "impl": p.ImplStatements, "parents": p.TypeList}, "params": p.TemplateParams}

    @_("MOD NAME LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "namespace", "name": p.NAME, "body": p.Statements}

    @_("LET LPAREN TypedNameList RPAREN ASSIGN LPAREN ExprList RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "define", "body": [{"type": "define", "name": name, "value": expr, "dataType": type, "mutable": mutable} for (name, type, mutable), expr in zip(p.TypedNameList, p.ExprList)]}

    @_("LET LPAREN TypedNameList RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "define", "body": [{"type": "define", "name": name, "value": None, "dataType": type, "mutable": mutable} for name, type, mutable in p.TypedNameList]}

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
        return {"type": "enum", "name": p.NAME, "body": p.EnumStatements, "dataType": None}

    @_("ENUM NAME COLON DataType LBRACE EnumStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "enum", "name": p.NAME, "body": p.EnumStatements, "dataType": p.DataType}

    @_("EXTERN STRING LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "extern", "linkage": p.STRING[1:-1], "body": p.Statements}

    @_("LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "scope", "body": p.Statements}

    @_("Expr SEMICOLON")
    def Statement(self, p):
        return p.Expr

    @_("QualifiedName")
    def DataType(self, p):
        return p.QualifiedName

    @_("DataType MUL")
    def DataType(self, p):
        return {"type": "pointer", "value": p.DataType}

    @_("DataType BITWISE_AND")
    def DataType(self, p):
        return {"type": "reference", "value": p.DataType}

    @_("DataType LESS TypeList GREATER")
    def DataType(self, p):
        return {"type": "template", "value": p.DataType, "params": p.TypeList}

    @_("FUNC LPAREN FuncParams RPAREN ARROW DataType")
    def DataType(self, p):
        return {"type": "function", "return": p.DataType, "params": [i["type"] for i in p.FuncParams]}

    @_("FUNC LPAREN FuncParams RPAREN")
    def DataType(self, p):
        return {"type": "function", "return": "void", "params": [i["type"] for i in p.FuncParams]}

    @_("FUNC LPAREN TypeList RPAREN ARROW DataType")
    def DataType(self, p):
        return {"type": "function", "return": p.DataType, "params": p.TypeList}

    @_("FUNC LPAREN TypeList RPAREN")
    def DataType(self, p):
        return {"type": "function", "return": "void", "params": p.TypeList}

    @_("NAME LBRACKET RBRACKET")
    def ArrayName(self, p):
        return {"type": "array", "value": None, "size": None}, p.NAME

    @_("NAME LBRACKET INTEGER RBRACKET")
    def ArrayName(self, p):
        value = p.INTEGER

        for signed in ["i", "u"]:
            if signed in value:
                value, bits = p.INTEGER.split(signed)
                assert bits in ["8", "16", "32", "64", "128"], f"Invalid integer bit size: '{bits}'."

        base = 16 if value.startswith("0x") else (8 if value.startswith("0o") else (2 if value.startswith("0b") else 10))
        return {"type": "array", "value": None, "size": int(value[2:] if base != 10 else value, base)}, p.NAME

    @_("ArrayName LBRACKET RBRACKET")
    def ArrayName(self, p):
        return {"type": "array", "value": p.ArrayName[0], "size": None}, p.ArrayName[1]

    @_("ArrayName LBRACKET INTEGER RBRACKET")
    def ArrayName(self, p):
        value = p.INTEGER

        for signed in ["i", "u"]:
            if signed in value:
                value, bits = p.INTEGER.split(signed)
                assert bits in ["8", "16", "32", "64", "128"], f"Invalid integer bit size: '{bits}'."

        base = 16 if value.startswith("0x") else (8 if value.startswith("0o") else (2 if value.startswith("0b") else 10))
        return {"type": "array", "value": p.ArrayName[0], "size": int(value[2:] if base != 10 else value, base)}, p.ArrayName[1]

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

    @_("PLUS", "MINUS", "MUL", "DIV", "MOD", "LESS LESS", "GREATER GREATER", "BITWISE_XOR", "AND", "OR", "BITWISE_AND", "BITWISE_OR", "BITWISE_NOT", "EQUAL", "NOT_EQUAL",
       "GREATER", "LESS", "GREATER_EQUAL", "LESS_EQUAL", "ARROW", "NOT", "ASSIGN", "LPAREN RPAREN", "LBRACKET RBRACKET", "NEW", "DEL", "DOUBLE_COLON", "COMMA",
       "PLUS_ASSIGN", "MINUS_ASSIGN", "MUL_ASSIGN", "DIV_ASSIGN", "MOD_ASSIGN", "LSHIFT_ASSIGN", "RSHIFT_ASSIGN", "XOR_ASSIGN", "AND_ASSIGN", "OR_ASSIGN")
    def FuncOperator(self, p):
        return "".join(p)

    @_("")
    def TypeList(self, p):
        return []

    @_("DataType")
    def TypeList(self, p):
        return [p.DataType]

    @_("TypeList COMMA DataType")
    def TypeList(self, p):
        p.TypeList.append(p.DataType)
        return p.TypeList

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

    @_("OPERATOR FuncOperator")
    def Expr(self, p):
        return {"type": "identifier", "value": f"op{p.FuncOperator}"}

    @_("Expr QUESTION_MARK Expr COLON Expr %prec TERNARY")
    def Expr(self, p):
        return {"type": "ternary", "condition": p.Expr0, "left": p.Expr1, "right": p.Expr2}

    @_("Expr DOT NAME", "Expr DOT OPERATOR FuncOperator")
    def Expr(self, p):
        return {"type": "get element", "value": p.Expr, "element": f"op{p.FuncOperator}" if len(p) > 3 else p.NAME}

    @_("Expr ARROW NAME", "Expr ARROW OPERATOR FuncOperator")
    def Expr(self, p):
        return {"type": "get element pointer", "value": p.Expr, "element": f"op{p.FuncOperator}" if len(p) > 3 else p.NAME}

    @_("Expr LPAREN ExprList RPAREN")
    def Expr(self, p):
        return {"type": "call", "value": p.Expr, "params": p.ExprList}
    
    @_("Expr LESS TypeList GREATER")
    def Expr(self, p):
        return {"type": "template", "value": p.Expr, "params": p.TypeList}

    # @_("DataType LPAREN ExprList RPAREN")
    # def Expr(self, p):
    #     return {"type": "call", "value": p.DataType, "params": p.ExprList}

    @_("Expr LBRACKET Expr RBRACKET")
    def Expr(self, p):
        return {"type": "get", "value": p.Expr0, "index": p.Expr1}

    @_("NEW DataType")
    def Expr(self, p):
        return {"type": "new", "value": p.DataType, "count": None, "params": None}

    @_("NEW DataType LPAREN ExprList RPAREN")
    def Expr(self, p):
        return {"type": "new", "value": p.DataType, "count": None, "params": p.ExprList}

    @_("NEW DataType LBRACKET Expr RBRACKET")
    def Expr(self, p):
        return {"type": "new", "value": p.DataType, "count": p.Expr, "params": None}

    @_("DEL Expr")
    def Expr(self, p):
        return {"type": "delete", "value": p.Expr, "array": False}

    @_("DEL LBRACKET RBRACKET Expr")
    def Expr(self, p):
        return {"type": "delete", "value": p.Expr, "array": True}

    @_("Expr AS DataType %prec CAST")
    def Expr(self, p):
        return {"type": "cast", "value": p.Expr, "target": p.DataType}

    @_("Expr AS LPAREN DataType RPAREN %prec CAST")
    def Expr(self, p):
        return {"type": "cast", "value": p.Expr, "target": p.DataType}

    @_("LBRACE ExprList RBRACE")
    def Expr(self, p):
        return {"type": "initializer list", "body": p.ExprList}

    @_("LBRACE ExprList RBRACE AS DataType %prec CAST")
    def Expr(self, p):
        return {"type": "list initialization", "name": p.DataType, "body": p.ExprList}

    @_("Expr PLUS Expr", "Expr MINUS Expr", "Expr MUL Expr", "Expr DIV Expr", "Expr MOD Expr",  "Expr BITWISE_XOR Expr",
       "Expr LESS LESS Expr %prec LSHIFT", "Expr GREATER GREATER Expr %prec RSHIFT", "Expr AND Expr", "Expr OR Expr", "Expr BITWISE_AND Expr", "Expr BITWISE_OR Expr",
       "Expr GREATER Expr", "Expr GREATER_EQUAL Expr", "Expr LESS Expr", "Expr LESS_EQUAL Expr", "Expr NOT_EQUAL Expr", "Expr EQUAL Expr")
    def Expr(self, p):
        return {"type": "expression", "operator": p[1] + p[2] if len(p) > 3 else p[1], "left": p.Expr0, "right": p.Expr1}

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
        return {"type": "string", "value": p.STRING[1:-1].encode("utf-8").decode("unicode_escape")}

    @_("CHAR")
    def Expr(self, p):
        char = p.CHAR[1:-1].encode("utf-8").decode("unicode_escape")
        assert len(char) == 1, "Expected a single character."
        return {"type": "i8", "value": ord(char)}

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

    @_("MINUS Expr %prec UNARY_MINUS")
    def Expr(self, p):
        return {"type": "negate", "value": p.Expr}

    @_("BITWISE_AND Expr %prec ADDRESS_OF")
    def Expr(self, p):
        return {"type": "address of", "value": p.Expr}

    @_("MUL Expr %prec DEREFERENCE")
    def Expr(self, p):
        return {"type": "dereference", "value": p.Expr}

    @_("NAME", "OPERATOR FuncOperator")
    def QualifiedName(self, p):
        return "".join(p)

    @_("QualifiedName DOUBLE_COLON NAME", "QualifiedName DOUBLE_COLON OPERATOR FuncOperator")
    def QualifiedName(self, p):
        return "".join(p)