import sly

from lexer import Lexer

class Parser(sly.Parser):
    tokens = Lexer.tokens
    error = lambda self, token: self.Error(token)

    precedence = (
        ("nonassoc", EQUAL, NOT_EQUAL, LESS, LESS_EQUAL, GREATER, GREATER_EQUAL),
        ("left", PLUS, MINUS),
        ("left", ASTERISK, SLASH),
        ("left", LSHIFT, RSHIFT),
        ("right", NOT, BITWISE_NOT),
        ("right", UNARY_MINUS, REFERENCE, DEREFERENCE),
        ("left", DOT, ARROW)
    )

    def __init__(self):
        self.ast = {"type": "module", "body": []}
        self.currentAccess = "public"

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

    @_("PUBLIC ComplexName COLON DataType", "PRIVATE ComplexName COLON DataType")
    def MemberStatement(self, p):
        return {"value": None, "dataType": p.DataType, "private": True if p[0] != "pub" else False}, p.ComplexName

    @_("PUBLIC ComplexName COLON DataType EQUALS Expr", "PRIVATE ComplexName COLON DataType EQUALS Expr")
    def MemberStatement(self, p):
        return {"value": p.Expr, "dataType": p.DataType, "private": True if p[0] != "pub" else False}, p.ComplexName

    @_("")
    def ImplStatements(self, p):
        return []

    @_("ImplStatement")
    def ImplStatements(self, p):
        return []

    @_("ImplStatements ImplStatement")
    def ImplStatements(self, p):
        p.ImplStatements.append(p.ImplStatement)
        return p.ImplStatements

    @_("DEST LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "destructor", "body": p.Statements, "params": p.FuncParams}

    @_("DEST LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "destructor", "body": [], "params": p.FuncParams}

    @_("CONST LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "constructor", "body": p.Statements, "params": p.FuncParams}

    @_("CONST LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "constructor", "body": [], "params": p.FuncParams}

    @_("OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "operator", "return": p.DataType, "operator": p.FuncOperator, "body": p.Statements, "params": p.FuncParams}

    @_("OPERATOR FuncOperator LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "operator", "return": p.DataType, "operator": p.FuncOperator, "body": [], "params": p.FuncParams}
    
    @_("OPERATOR FuncOperator LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "operator", "operator": p.FuncOperator, "body": p.Statements, "params": p.FuncParams}

    @_("OPERATOR FuncOperator LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "operator", "operator": p.FuncOperator, "body": [], "params": p.FuncParams}

    @_("PUBLIC ComplexName LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE", "PRIVATE ComplexName LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.ComplexName, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC ComplexName LPAREN FuncParams RPAREN ARROW DataType SEMICOLON", "PRIVATE ComplexName LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.ComplexName, "body": [], "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC ComplexName LPAREN FuncParams RPAREN LBRACE Statements RBRACE", "PRIVATE ComplexName LPAREN FuncParams RPAREN LBRACE Statements RBRACE")
    def ImplStatement(self, p):
        return {"type": "func", "name": p.ComplexName, "body": p.Statements, "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("PUBLIC ComplexName LPAREN FuncParams RPAREN SEMICOLON", "PRIVATE ComplexName LPAREN FuncParams RPAREN SEMICOLON")
    def ImplStatement(self, p):
        return {"type": "func", "name": p.ComplexName, "body": [], "params": p.FuncParams, "private": True if p[0] != "pub" else False}

    @_("TypedName")
    def TypedNameList(self, p):
        return [p.TypedName]

    @_("TypedNameList COMMA TypedName")
    def TypedNameList(self, p):
        p.TypedNameList.append(p.TypedName)
        return p.TypedNameList

    @_("ComplexName COLON DataType")
    def TypedName(self, p):
        return (p.ComplexName, p.DataType)

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

    @_("INCLUDE IncludeParams SEMICOLON")
    def Statement(self, p):
        return {"type": "include", "modules": p.IncludeParams, "identifiers": [], "namespace": True, "all": True}

    @_("INCLUDE IncludeParams COLON IncludeParams SEMICOLON")
    def Statement(self, p):
        return {"type": "include", "modules": p.IncludeParams0, "identifiers": p.IncludeParams1, "namespace": False, "all": False}

    @_("INCLUDE IncludeParams COLON ASTERISK SEMICOLON")
    def Statement(self, p):
        return {"type": "include", "modules": p.IncludeParams, "identifiers": [], "namespace": False, "all": True}

    @_("FUNC LPAREN FuncParams RPAREN ARROW ComplexNameTilde LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "func", "return": None, "name": p.ComplexNameTilde, "body": p.Statements, "params": p.FuncParams}

    @_("FUNC LPAREN FuncParams RPAREN ARROW ComplexNameTilde SEMICOLON")
    def Statement(self, p):
        return {"type": "func", "return": None, "name": p.ComplexNameTilde, "body": [], "params": p.FuncParams}

    @_("FUNC ComplexName LPAREN FuncParams RPAREN ARROW DataType LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.ComplexName, "body": p.Statements, "params": p.FuncParams}

    @_("FUNC ComplexName LPAREN FuncParams RPAREN ARROW DataType SEMICOLON")
    def Statement(self, p):
        return {"type": "func", "return": p.DataType, "name": p.ComplexName, "body": [], "params": p.FuncParams}

    @_("IF Expr LBRACE Statements RBRACE ElseStatement")
    def Statement(self, p):
        return {"type": "if", "condition": p.Expr, "body": p.Statements, "else": p.ElseStatement}

    @_("WHILE Expr LBRACE Statements RBRACE ElseStatement")
    def Statement(self, p):
        return {"type": "while", "condition": p.Expr, "body": p.Statements, "else": p.ElseStatement}

    @_("FOR ExprLikeStatement SEMICOLON ExprOrNone SEMICOLON ExprLikeStatement LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "for", "declaration": [p.ExprLikeStatement0], "condition": p.ExprOrNone, "iteration": [p.ExprLikeStatement1], "body": p.Statements}

    @_("CLASS ComplexName LBRACE MemberStatements RBRACE IMPL LBRACE ImplStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "class", "name": p.ComplexName, "members": p.MemberStatements, "impl": p.ImplStatements}

    @_("CLASS ComplexName LESS TemplateParams GREATER LBRACE MemberStatements RBRACE IMPL LBRACE ImplStatements RBRACE SEMICOLON")
    def Statement(self, p):
        return {"type": "template", "body": {"type": "class", "name": p.ComplexName, "members": p.MemberStatements, "impl": p.ImplStatements}, "params": p.TemplateParams}

    @_("DO LBRACE Statements RBRACE WHILE LPAREN Expr RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "do while", "condition": p.Expr, "body": p.Statements}

    @_("DO LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "do", "body": p.Statements}

    @_("MOD ComplexName LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "namespace", "name": p.ComplexName, "body": p.Statements}

    @_("LBRACE Statements RBRACE")
    def Statement(self, p):
        return {"type": "scope", "body": p.Statements}

    @_("Expr EQUALS Expr SEMICOLON")
    def Statement(self, p):
        return {"type": "assign", "left": p.Expr0, "right": p.Expr1}

    @_("Expr EqualsOperator Expr SEMICOLON")
    def Statement(self, p):
        return {"type": "assign", "left": p.Expr0, "right": {"type": "expression", "operator": p.EqualsOperator, "left": p.Expr0, "right": p.Expr1}}

    @_("LPAREN ExprList RPAREN EQUALS LPAREN ExprList RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "do", "body": [{"type": "assign", "left": left, "right": right} for left, right in zip(p.ExprList0, p.ExprList1)], "scope": False}

    @_("LET LPAREN TypedNameList RPAREN EQUALS LPAREN ExprList RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "do", "body": [{"type": "define", "name": name, "value": expr, "dataType": type} for (name, type), expr in zip(p.TypedNameList, p.ExprList)], "scope": False}

    @_("LET ComplexName COLON DataType EQUALS Expr SEMICOLON")
    def Statement(self, p):
        return {"type": "define", "name": p.ComplexName, "value": p.Expr, "dataType": p.DataType}

    @_("LET ComplexName COLON DataType SEMICOLON")
    def Statement(self, p):
        return {"type": "define", "name": p.ComplexName, "value": None, "dataType": p.DataType}

    @_("FuncExpr LPAREN CallParams RPAREN SEMICOLON")
    def Statement(self, p):
        return {"type": "call", "value": p.FuncExpr, "params": p.CallParams}

    @_("TYPE ComplexName EQUALS DataType SEMICOLON")
    def Statement(self, p):
        return {"type": "typedef", "name": p.ComplexName, "value": p.DataType}

    @_("ExprLikeStatementList SEMICOLON")
    def Statement(self, p):
        return {"type": "expression", "body": p.ExprLikeStatementList}

    @_("SEMICOLON")
    def Statement(self, p):
        return

    @_("")
    def Statement(self, p):
        return

    @_("NAME")
    def DataType(self, p):
        return p.NAME

    @_("DataType ASTERISK")
    def DataType(self, p):
        return {"type": "pointer", "value": p.DataType}

    @_("DataType LESS TypeParams GREATER")
    def DataType(self, p):
        return {"type": "template", "value": p.DataType, "params": p.TypeParams}

    @_("LBRACKET DataType RBRACKET")
    def DataType(self, p):
        return {"type": "array", "value": p.DataType, "size": None}

    @_("LBRACKET DataType SEMICOLON INTEGER RBRACKET")
    def DataType(self, p):
        base = 16 if p.INTEGER.startswith("0x") else (8 if p.INTEGER.startswith("0o") else (2 if p.INTEGER.startswith("0b") else 10))
        return {"type": "array", "value": p.DataType, "size": int(p.INTEGER.replace("0x", "").replace("0o", "").replace("0b", ""), base)}

    @_("FUNC LPAREN FuncTypeParams RPAREN ARROW DataType")
    def DataType(self, p):
        return {"type": "function", "return": p.DataType, "params": p.FuncTypeParams}

    @_("FuncTypeParam")
    def FuncTypeParams(self, p):
        return [p.FuncTypeParam]

    @_("FuncTypeParams COMMA FuncTypeParam")
    def FuncTypeParams(self, p):
        p.FuncTypeParams.append(p.FuncTypeParam)
        return p.FuncTypeParams

    @_("DataType")
    def FuncTypeParam(self, p):
        return p.DataType

    @_("THREE_DOT")
    def FuncTypeParam(self, p):
        return "three dot"

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

    @_("FuncParams COMMA FuncParam")
    def FuncParams(self, p):
        p.FuncParams.append(p.FuncParam)
        return p.FuncParams

    @_("FuncParam")
    def FuncParams(self, p):
        return [p.FuncParam]

    @_("NAME COLON DataType")
    def FuncParam(self, p):
        return {"type": p.DataType, "name": p.NAME}

    @_("THREE_DOT")
    def FuncParam(self, p):
        return {"type": "three dot"}

    @_("PLUS", "MINUS", "ASTERISK", "SLASH", "MOD", "LSHIFT", "RSHIFT", "XOR", "AND", "OR", "BITWISE_AND", "BITWISE_OR", "BITWISE_NOT", "EQUAL", "NOT_EQUAL",
       "GREATER", "LESS", "GREATER_EQUAL", "LESS_EQUAL", "ARROW", "NOT", "EQUALS", "LPAREN RPAREN", "LBRACKET RBRACKET", "NEW", "DELETE", "COLON COLON", "COMMA")
    def FuncOperator(self, p):
        return "".join(p)
    
    @_("EqualsOperator")
    def FuncOperator(self, p):
        return f"{p.EqualsOperator}="
    
    @_("PLUS EQUALS", "MINUS EQUALS", "ASTERISK EQUALS", "SLASH EQUALS", "MOD EQUALS", "LSHIFT EQUALS", "RSHIFT EQUALS", "XOR EQUALS", "BITWISE_AND EQUALS", "BITWISE_OR EQUALS")
    def EqualsOperator(self, p):
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

    @_("NAME EQUALS Expr")
    def TemplateParam(self, p):
        return {"name": p.NAME, "value": p.Expr}

    @_("Expr")
    def ExprOrNone(self, p):
        return p.Expr

    @_("")
    def ExprOrNone(self, p):
        return

    @_("ExprLikeStatement")
    def ExprLikeStatementList(self, p):
        return [p.ExprLikeStatement]

    @_("ExprLikeStatementList COMMA ExprLikeStatement")
    def ExprLikeStatementList(self, p):
        p.ExprLikeStatementList.append(p.ExprLikeStatement)
        return p.ExprLikeStatementList

    @_("Expr EQUALS Expr")
    def ExprLikeStatement(self, p):
        return {"type": "assign", "left": p.Expr0, "right": p.Expr1}

    @_("Expr EqualsOperator Expr")
    def ExprLikeStatement(self, p):
        return {"type": "assign", "left": p.Expr0, "right": {"type": "expression", "operator": p.EqualsOperator, "left": p.Expr0, "right": p.Expr1}}

    @_("LPAREN ExprList RPAREN EQUALS LPAREN ExprList RPAREN")
    def ExprLikeStatement(self, p):
        return {"type": "do", "body": [{"type": "assign", "left": left, "right": right} for left, right in zip(p.ExprList0, p.ExprList1)], "scope": False}

    @_("LET LPAREN TypedNameList RPAREN EQUALS LPAREN ExprList RPAREN")
    def ExprLikeStatement(self, p):
        return {"type": "do", "body": [{"type": "define", "name": name, "value": expr, "dataType": type} for (name, type), expr in zip(p.TypedNameList, p.ExprList)], "scope": False}

    @_("LET ComplexName COLON DataType EQUALS Expr")
    def ExprLikeStatement(self, p):
        return {"type": "define", "name": p.ComplexName, "value": p.Expr, "dataType": p.DataType}

    @_("LET ComplexName COLON DataType")
    def ExprLikeStatement(self, p):
        return {"type": "define", "name": p.ComplexName, "value": None, "dataType": p.DataType}

    @_("")
    def ExprLikeStatement(self, p):
        return

    @_("LPAREN Expr RPAREN")
    def FuncExpr(self, p):
        return p.Expr

    @_("ComplexName")
    def FuncExpr(self, p):
        return {"type": "identifier", "value": p.ComplexName}

    @_("FuncExpr DOT NAME")
    def FuncExpr(self, p):
        return {"type": "get element", "value": p.FuncExpr, "element": p.NAME}

    @_("FuncExpr ARROW NAME")
    def FuncExpr(self, p):
        return {"type": "get element pointer", "value": p.FuncExpr, "element": p.NAME}

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

    @_("FuncExpr")
    def Expr(self, p):
        return p.FuncExpr

    @_("FuncExpr LPAREN CallParams RPAREN")
    def Expr(self, p):
        return {"type": "call", "value": p.FuncExpr, "params": p.CallParams}

    @_("Expr LBRACKET Expr RBRACKET")
    def Expr(self, p):
        return {"type": "get", "value": p.Expr0, "index": p.Expr1}

    @_("LPAREN DataType RPAREN Expr")
    def Expr(self, p):
        return {"type": "cast", "value": p.Expr, "target": p.DataType}

    @_("LBRACE ExprList RBRACE")
    def Expr(self, p):
        return {"type": "initializer list", "body": p.ExprList}

    @_("Expr PLUS Expr", "Expr MINUS Expr", "Expr ASTERISK Expr", "Expr SLASH Expr", "Expr MOD Expr",  "Expr XOR Expr",
       "Expr LSHIFT Expr", "Expr RSHIFT Expr", "Expr AND Expr", "Expr OR Expr", "Expr BITWISE_AND Expr", "Expr BITWISE_OR Expr",
       "Expr GREATER Expr", "Expr GREATER_EQUAL Expr", "Expr LESS Expr", "Expr LESS_EQUAL Expr", "Expr NOT_EQUAL Expr", "Expr EQUAL Expr")
    def Expr(self, p):
        return {"type": "expression", "operator": p[1], "left": p.Expr0, "right": p.Expr1}

    @_("INTEGER")
    def Expr(self, p):
        base = 16 if p.INTEGER.startswith("0x") else (8 if p.INTEGER.startswith("0o") else (2 if p.INTEGER.startswith("0b") else 10))
        return {"type": "i32", "value": int(p.INTEGER.replace("0x", "").replace("0o", "").replace("0b", ""), base)}

    @_("FLOAT")
    def Expr(self, p):
        return {"type": "float" if p.FLOAT.endswith("f") else "double", "value": float(p.FLOAT.replace("f", ""))}

    @_("STRING")
    def Expr(self, p):
        return {"type": "string", "value": p.STRING[1:-1].replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").replace("\\0", "\0").replace("\\'", "'").replace('\\"', '"')}

    @_("CHAR")
    def Expr(self, p):
        char = p.CHAR[1:-1].replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").replace("\\0", "\0").replace("\\'", "'").replace('\\"', '"')
        assert len(char) == 1, "Expected a single character."
        return {"type": "i8", "value": ord(char)}

    @_("TRUE", "FALSE", "NULL")
    def Expr(self, p):
        return {"type": "bool" if p[0] != "null" else "i64", "value": 0 if p[0] != "true" else 1}

    @_("NOT Expr")
    def Expr(self, p):
        return {"type": "not", "value": p.Expr}

    @_("BITWISE_NOT Expr")
    def Expr(self, p):
        return {"type": "bitwise not", "value": p.Expr}

    @_("MINUS Expr %prec UNARY_MINUS")
    def Expr(self, p):
        return {"type": "negate", "value": p.Expr}

    @_("BITWISE_AND Expr %prec REFERENCE")
    def Expr(self, p):
        return {"type": "reference", "value": p.Expr}

    @_("ASTERISK Expr %prec DEREFERENCE")
    def Expr(self, p):
        return {"type": "dereference", "value": p.Expr}

    @_("NAME")
    def ComplexName(self, p):
        return p.NAME

    @_("ComplexName COLON COLON NAME")
    def ComplexName(self, p):
        return f"{p.ComplexName}::{p.NAME}"

    @_("ComplexName COLON COLON NAME", "ComplexName COLON COLON BITWISE_NOT NAME")
    def ComplexNameTilde(self, p):
        return f"{p.ComplexName}::{"~" if len(p) > 4 else ""}{p.NAME}"