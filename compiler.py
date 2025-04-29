import os

from llvmlite import ir

from lexer import Lexer
from parser import Parser

class Scope:
    def __init__(self, name):
        self.__variables, self.__name = {}, name

    @property
    def Name(self):
        return self.__name
    
    def Copy(self):
        scope = Scope(self.__name)
        scope.__variables = self.__variables.copy()
        return scope
    
    def Has(self, name, uuid = None):
        assert not name.count("@") > 1, "Invalid name."
        if "@" in name: name, uuid = name.split("@")
        if uuid is None: return len([i for i in self.__variables if i.split("@")[0] == name]) > 0
        return f"{name}@{uuid}" in self.__variables

    def Set(self, name, value, uuid = None):
        assert not name.count("@") > 1, "Invalid name."
        if "@" in name: name, uuid = name.split("@")
        self.__variables[(name if uuid is None else f"{name}@{uuid}")] = value

    def Get(self, name, uuid = None):
        if "@" in name:
            assert not name.count("@") > 1, "Invalid name."
            name, uuid = name.split("@")

        if uuid is None:
            variables = [self.__variables[i] for i in self.__variables if i.split("@")[0] == name]
            assert len(variables) != 0, f"Unknown variable '{name}'."
            return variables if len(variables) > 1 else variables[0]

        assert self.Has(name, uuid), f"Unknown variable '{name}@{uuid}'."
        return self.__variables[f"{name}@{uuid}"]

class ScopeManager:
    def __init__(self, compiler):
        self.__compiler = compiler
        self.__scopes, self.__namespaces = [], []
        self.__recordState, self.__record = False, []
        self.__class = None

    @property
    def Global(self):
        return self.__scopes[0]

    def PopUntilGlobal(self):
        while self.Scope != self.Global:
            self.PopScope()
    
    @property
    def Scope(self):
        return self.__scopes[-1]

    def PushScope(self, scope):
        self.__scopes.append(scope)

    def PopScope(self):
        assert len(self.__scopes) > 0, "No scope to pop."
        return self.__scopes.pop()
    
    @property
    def Namespace(self):
        return "::".join(self.__namespaces)
    
    def PushNamespace(self, name):
        self.__namespaces += name.split("::")

    def PopNamespace(self):
        assert len(self.__namespaces) > 0, "No namespace to pop."
        return self.__namespaces.pop()
    
    @property
    def Class(self):
        return self.__class
    
    def PushClass(self, _class):
        self.__class = _class
        _class.OnAttach()

    def PopClass(self):
        assert self.__class is not None, "No class to pop."
        _class, self.__class = self.__class, None
        _class.OnDetach(); return _class
    
    def Record(self):
        self.__revert = [scope.Copy() for scope in self.__scopes]
        self.__recordState, self.__record = True, []

    def Revert(self):
        assert self.__recordState, "No record to revert."
        self.__recordState, self.__scopes = False, self.__revert
        return self.__record
    
    def Has(self, name, uuid = None):
        potentials = [[]]

        for i in self.__namespaces:
            potentials.append(potentials[-1] + [i])

        for namespace in potentials[::-1]:
            actualName = "::".join(namespace + [name])

            for scope in self.__scopes[::-1]:
                if scope.Has(actualName, uuid):
                    return True
            
        return False
    
    def Set(self, name, value, force = False, uuid = None):
        potentials = [[]]

        for i in self.__namespaces:
            potentials.append(potentials[-1] + [i])

        for namespace in potentials[::-1]:
            actualName = "::".join(namespace + [name])

            for scope in ([] if force else self.__scopes[::-1]):
                if scope.Has(actualName, uuid):
                    return scope.Set(actualName, value, uuid)

        assert "::" not in name, "Can't define a variable with namespace."

        if self.Scope == self.Global:
            name = "::".join(self.__namespaces + [name])
            if self.__recordState: self.__record += [(name, value, uuid)]

        if isinstance(value, Class):
            value.OnDetach()

        self.Scope.Set(name, value, uuid)

    def Get(self, name, uuid = None):
        potentials = [[]]

        for i in self.__namespaces:
            potentials.append(potentials[-1] + [i])

        for namespace in potentials[::-1]:
            actualName = "::".join(namespace + [name])

            for scope in self.__scopes[::-1]:
                if scope.Has(actualName, uuid):
                    return scope.Get(actualName, uuid)

class Class:
    def __init__(self, compiler, name):
        self.__compiler, self.__name = compiler, name
        self.__elements, self.__functions = {}, {}

    @property
    def Name(self):
        return self.__name
    
    @property
    def Elements(self):
        return self.__elements.copy()
    
    @property
    def Functions(self):
        return self.__functions.copy()
    
    def OnAttach(self):
        self.type = ir.global_context.get_identified_type(self.__name)

    def OnDetach(self):
        if self.type.elements is not None: return
        sizeof = self.__compiler.scopeManager.Get("sizeof")
        alignof = self.__compiler.scopeManager.Get("alignof")
        elements, offset, alignment = {}, 0, 0

        for i in self.__elements:
            alignment = max(alignment, alignof(self.__elements[i]["type"]).constant)

        self.__elements.update({None: ...})

        for i in self.__elements:
            size = sizeof(self.__elements[i]["type"]).constant if i is not None else 0

            for j in [alignment, alignof(self.__elements[i]["type"]).constant if i is not None else 0]:
                if not j > 0: continue
                if (offset % j) != 0 and (i is None or (offset % j) + size > j):
                    padding = j - (offset % j)
                    elements[f"<p@{hash(offset)}:{padding}>"] = {"type": ir.ArrayType(ir.IntType(8), padding), "value": None, "access": None}
                    offset += padding

            if i is not None:
                elements[i] = self.__elements[i]
                offset += size

        self.__elements = elements.copy()
        self.type.set_body(*[i["type"] for i in self.__elements.values()])

    def RegisterElement(self, name, value):
        self.__elements[name] = value

    def RegisterFunction(self, name, value):
        self.__functions[name] = value

    def Index(self, name):
        return list(self.__elements.keys()).index(name)
    
    def Has(self, name):
        return name in self.__elements or name in self.__functions
    
    def Get(self, name):
        return self.__elements[name] if name in self.__elements else self.__functions[name]

class Template:
    def __init__(self, compiler, body, params):
        self.__compiler = compiler
        self.__body, self.__params = body, params
        self.__instances = {}

    def Get(self, params):
        params = [self.__compiler.VisitType(i) for i in params]

        if tuple(params) in self.__instances:
            return self.__instances[tuple(params)]
        
        assert len(self.__params) == len(params), "Parameter count mismatch."
        self.__compiler.scopeManager.Record()
        self.__compiler.scopeManager.PopUntilGlobal()

        for index, i in enumerate(self.__params):
            self.__compiler.scopeManager.Set(i["name"], params[index], force = True)

        self.__body["name"] = f"{self.__body["name"]}@{hash(tuple(params))}"
        self.__instances[tuple(params)] = self.__compiler.Compile([self.__body])
        variables, _class = self.__compiler.scopeManager.Revert(), None

        for i in variables:
            if i[0] == self.__body["name"]: _class = i[1]
            if not i[0].startswith(self.__body["name"]): continue
            self.__compiler.scopeManager.Global.Set(i[0], i[1], i[2])

        return _class.type

class CompileTimeFunction:
    def __init__(self, compiler):
        self.compiler = compiler

class SizeOf(CompileTimeFunction):
    def __init__(self, compiler):
        super().__init__(compiler)

    def __call__(self, value):
        try:
            type = self.compiler.VisitType(value)

        except:
            type = self.compiler.VisitValue(value).type

        if isinstance(type, ir.ArrayType):
            return ir.Constant(ir.IntType(32), type.count * self(type.element).constant)
        
        elif isinstance(type, ir.BaseStructType):
            return ir.Constant(ir.IntType(32), sum([self(i).constant for i in type.elements]))
        
        elif isinstance(type, ir.PointerType):
            return ir.Constant(ir.IntType(32), 8)
        
        elif isinstance(type, ir.IntType):
            return ir.Constant(ir.IntType(32), type.width // 8)
        
        elif isinstance(type, ir.FloatType):
            return ir.Constant(ir.IntType(32), 4)
        
        elif isinstance(type, ir.DoubleType):
            return ir.Constant(ir.IntType(32), 8)
        
        else:
            assert False, "Unknown type."

class AlignOf(CompileTimeFunction):
    def __init__(self, compiler):
        super().__init__(compiler)

    def __call__(self, value):
        try:
            type = self.compiler.VisitType(value)

        except:
            type = self.compiler.VisitValue(value).type

        if isinstance(type, ir.ArrayType):
            return ir.Constant(ir.IntType(32), self(type.element).constant)
        
        elif isinstance(type, ir.BaseStructType):
            return ir.Constant(ir.IntType(32), max([self(i).constant for i in type.elements]))
        
        elif isinstance(type, ir.PointerType):
            return ir.Constant(ir.IntType(32), 8)
        
        elif isinstance(type, ir.IntType):
            return ir.Constant(ir.IntType(32), type.width // 8)
        
        elif isinstance(type, ir.FloatType):
            return ir.Constant(ir.IntType(32), 4)
        
        elif isinstance(type, ir.DoubleType):
            return ir.Constant(ir.IntType(32), 8)
        
        else:
            assert False, "Unknown type."

class OffsetOf(CompileTimeFunction):
    def __init__(self, compiler):
        super().__init__(compiler)

    def __call__(self, value, element):
        try:
            type = self.compiler.VisitType(value)

        except:
            type = self.compiler.VisitValue(value).type

        assert isinstance(type, ir.BaseStructType), "Expected a class."
        assert element["type"] == "identifier", "Expected an identifier."
        _class, sizeof = self.compiler.scopeManager.Get(type.name), self.compiler.scopeManager.Get("sizeof")
        return ir.Constant(ir.IntType(32), sum([sizeof(i).constant for i in type.elements[:_class.Index(element["value"])]]))

class DeclType(CompileTimeFunction):
    def __init__(self, compiler):
        super().__init__(compiler)

    def __call__(self, value):
        return self.compiler.VisitValue(value).type

class Compiler:
    def __init__(self):
        self.includePaths = []
        self.module = ir.Module("main")
        self.scopeManager = ScopeManager(self)
        self.scopeManager.PushScope(Scope("global"))
        self.scopeManager.Set("bool", ir.IntType(1), force = True)
        self.scopeManager.Set("i8", ir.IntType(8), force = True)
        self.scopeManager.Set("i16", ir.IntType(16), force = True)
        self.scopeManager.Set("i32", ir.IntType(32), force = True)
        self.scopeManager.Set("i64", ir.IntType(64), force = True)
        self.scopeManager.Set("float", ir.FloatType(), force = True)
        self.scopeManager.Set("double", ir.DoubleType(), force = True)
        self.scopeManager.Set("void", ir.VoidType(), force = True)
        self.scopeManager.Set("sizeof", SizeOf(self), force = True)
        self.scopeManager.Set("alignof", AlignOf(self), force = True)
        self.scopeManager.Set("offsetof", OffsetOf(self), force = True)
        self.scopeManager.Set("decltype", DeclType(self), force = True)
        self.builderStack, self.scopeTest = [], True
        self.__includedFiles = []

    def __del__(self):
        self.scopeManager.PopScope()
    
    @property
    def Builder(self) -> ir.builder.IRBuilder:
        if len(self.builderStack) < 1: return None
        return self.builderStack[-1]
    
    def PushBuilder(self, builder):
        self.builderStack.append(builder)

    def PopBuilder(self):
        assert len(self.builderStack) > 0, "No builder to pop."
        return self.builderStack.pop()

    def InvokeDestructors(self):
        for name, value in self.scopeManager.Scope._Scope__variables.items():
            if hasattr(value, "type") and value.type.is_pointer and isinstance(value.type.pointee, ir.BaseStructType):
                self.VisitDestructor(self.scopeManager.Get(value.type.pointee.name), value)

    def Compile(self, ast):
        for node in ast:
            if node is None: continue
            if self.Builder is not None and self.Builder.block.is_terminated: break
            name = f"Visit{"".join([i.capitalize() for i in node["type"].split(" ")])}"
            assert hasattr(self, name), f"Unknown node '{node["type"]}'."
            getattr(self, name)(node)

        return self.module
    
    def VisitTemplate(self, node):
        assert node["body"]["type"] in ["class", "func"], "Expected a function or a class."
        self.scopeManager.Set(node["body"]["name"], Template(self, node["body"], node["params"]))
    
    def VisitClass(self, node):
        assert self.scopeManager.Scope == self.scopeManager.Global or not self.scopeTest, "Classes must be defined in global scope."
        self.scopeManager.PushClass(Class(self, node["name"]))
        self.scopeManager.PushNamespace(node["name"])
        impl = []

        for name, member in node["members"].items():
            self.scopeManager.Class.RegisterElement(name, {"type": self.VisitType(member["dataType"]), "value": self.VisitValue(member["value"]), "access": "private" if member["private"] else "public"})

        for i in node["impl"]:
            if i["type"] in ["constructor", "destructor"]:
                i = {"type": "func", "name": ("" if i["type"] != "destructor" else "~") + node["name"], "params": i["params"], "body": i["body"], "private": False}

            if i["type"] in ["operator"]:
                i = {"type": "func", "name": f"operator{i['operator']}", "params": i["params"], "body": i["body"], "private": False}

            if "return" not in i or i["return"] is None: i["return"] = "void"
            i["params"] = [{"type": self.scopeManager.Class.type.as_pointer(), "name": "this"}] + i["params"]
            self.scopeManager.Class.RegisterFunction(i["name"], {"type": self.VisitFunc(i, body = False), "access": "private" if i["private"] else "public"})
            impl.append(i)

        self.scopeManager.PopNamespace()
        self.scopeManager.Set(node["name"], self.scopeManager.Class, force = True)
        self.scopeManager.PushNamespace(node["name"])

        for i in impl:
            func = self.VisitFunc(i, override = True)
            self.scopeManager.Class.RegisterFunction(i["name"], {"type": func, "access": "private" if i["private"] else "public"})
            self.scopeManager.Set(i["name"], func, force = True)

        self.scopeManager.PopNamespace()
        self.scopeManager.PopClass()
    
    def VisitInclude(self, node):
        assert self.scopeManager.Scope == self.scopeManager.Global or not self.scopeTest, "Includes must be made in global scope."

        for i in node["modules"]:
            source = None

            for j in ["./"] + self.includePaths:
                path = os.path.join(j, i)

                if os.path.exists(path):
                    if os.path.isfile(path):
                        if path in self.__includedFiles: return
                        else: self.__includedFiles.append(path)
                        source = open(path, "r").read()
                        break

                    else:
                        path = os.path.join(path, "entry.ai")
                        assert os.path.exists(path), "Module entry point not found."
                        if path in self.__includedFiles: return
                        else: self.__includedFiles.append(path)
                        source = open(path, "r").read()
                        break

            lexer, parser = Lexer(), Parser()
            assert source is not None, f"Module '{i}' not found."
            parser.parse(lexer.tokenize(source))

            if not node["all"]:
                self.scopeManager.Record()

            if node["namespace"]:
                self.scopeManager.PushNamespace(i.split(".")[0])

            self.Compile(parser.ast["body"])
            
            if node["namespace"]:
                self.scopeManager.PopNamespace()
                
            if not node["all"]:
                for name, value, uuid in self.scopeManager.Revert():
                    if name in node["identifiers"]:
                        self.scopeManager.Global.Set(name, value, uuid)
                        node["identifiers"].remove(name)

                for i in node["identifiers"]:
                    assert False, f"Unknown identifier '{i}'."

    def VisitNamespace(self, node):
        assert self.scopeManager.Scope == self.scopeManager.Global or not self.scopeTest, "Namespaces must be defined in global scope."
        self.scopeManager.PushNamespace(node["name"])
        self.Compile(node["body"])
        self.scopeManager.PopNamespace()
    
    def VisitDo(self, node):
        if node.get("scope", True):
            self.scopeManager.PushScope(Scope(node["type"]))

        self.Compile(node["body"])

        if node.get("scope", True):
            self.scopeManager.PopScope()

    def VisitDoWhile(self, node):
        self.scopeManager.PushScope(Scope(node["type"]))
        self.Compile(node["body"])
        self.scopeManager.PopScope()

        condition = self.VisitValue(node["condition"])
        whileBlock = self.Builder.append_basic_block()

        endBlock = self.Builder.append_basic_block()
        self.Builder.cbranch(condition, whileBlock, endBlock)
        self.Builder.position_at_start(whileBlock)

        self.scopeManager.PushScope(Scope(node["type"]))
        self.Compile(node["body"])
        self.scopeManager.PopScope()

        if not self.Builder.block.is_terminated:
            condition = self.VisitValue(node["condition"])
            self.Builder.cbranch(condition, whileBlock, endBlock)

        self.Builder.position_at_start(endBlock)
    
    def VisitScope(self, node):
        self.scopeManager.PushScope(Scope(node["type"]))
        self.Compile(node["body"])
        self.scopeManager.PopScope()
                
    def VisitFunc(self, node, body = True, override = False):
        assert self.scopeManager.Scope == self.scopeManager.Global or not self.scopeTest, "Functions must be defined in global scope."
        params, threeDots, structState = {}, False, False

        if not self.scopeManager.Class:
            names = node["name"].split("::")

            if len(names) > 1 and self.scopeManager.Has(names[-2]):
                _class = self.scopeManager.Get(names[-2])
                
                if isinstance(_class, Class):
                    assert _class.Has(names[-1]), f"Class '{names[-2]}' does not have function '{names[-1]}'."
                    node["params"] = [{"type": _class.type.as_pointer(), "name": "this"}] + node["params"]
                    self.scopeManager.PushClass(_class)
                    structState = True

        for i, param in enumerate(node["params"]):
            if param["type"] != "three dot":
                params[param["name"]] = self.VisitType(param["type"])

            else:
                assert i == len(node["params"]) - 1, "Three dots must be the last parameter."
                threeDots = True

        if not self.scopeManager.Has(node["name"], hash(tuple(params.values()))):
            name = f"{node["name"]}@{hash(tuple(params.values()))}" if self.scopeManager.Has(node["name"]) else node["name"]
            func = ir.Function(self.module, ir.FunctionType(self.VisitType(node["return"]), list(params.values()), threeDots), name)
            if self.scopeManager.Class: func.parent_struct = self.scopeManager.Class
            self.scopeManager.Set(node["name"], func, force = True, uuid = hash(tuple(params.values())))

        else:
            func = self.scopeManager.Get(node["name"], hash(tuple(params.values())))
            assert not (not override and func.blocks), f"Function '{node["name"]}' already defined."

        if node["body"] and body:
            self.PushBuilder(ir.IRBuilder(func.append_basic_block()))
            self.scopeManager.PushScope(Scope(node["type"]))

            for i, name in enumerate(params):
                ptr = self.Builder.alloca(params[name])
                self.Builder.store(func.args[i], ptr, self.scopeManager.Get("alignof")(func.args[i]).constant)
                self.scopeManager.Set(name, ptr, force = True)

            self.Compile(node["body"])

            if not self.Builder.block.is_terminated:
                assert func.return_value.type == ir.VoidType(), f"Function '{node["name"]}' must return a value."
                self.Builder.ret_void()

            self.scopeManager.PopScope()
            self.PopBuilder()

        if structState:
            self.scopeManager.PopClass()

        return func
        
    def VisitIf(self, node):
        endBlock, currentNode = None, node

        while currentNode:
            if "type" in currentNode:
                intermediateCheck = self.Builder.append_basic_block()
                ifBlock = self.Builder.append_basic_block()
                condition = self.VisitValue(currentNode["condition"])
                self.Builder.cbranch(condition, ifBlock, intermediateCheck)
                self.Builder.position_at_end(ifBlock)

                self.scopeManager.PushScope(Scope(node["type"]))
                self.Compile(currentNode["body"])
                self.scopeManager.PopScope()

                if not self.Builder.block.is_terminated:
                    if not currentNode["else"]["body"]: endBlock = intermediateCheck
                    if endBlock == None: endBlock = self.Builder.append_basic_block()
                    self.Builder.branch(endBlock)

                self.Builder.position_at_end(intermediateCheck)

            elif "else" in currentNode:
                intermediateCheck = self.Builder.append_basic_block()
                elseIfBlock = self.Builder.append_basic_block()
                condition = self.VisitValue(currentNode["condition"])
                self.Builder.cbranch(condition, elseIfBlock, intermediateCheck)
                self.Builder.position_at_end(elseIfBlock)

                self.scopeManager.PushScope(Scope(node["type"]))
                self.Compile(currentNode["body"])
                self.scopeManager.PopScope()

                if not self.Builder.block.is_terminated:
                    if not currentNode["else"]["body"]: endBlock = intermediateCheck
                    if endBlock == None: endBlock = self.Builder.append_basic_block()
                    self.Builder.branch(endBlock)

                self.Builder.position_at_end(intermediateCheck)

            else:
                self.scopeManager.PushScope(Scope(node["type"]))
                self.Compile(currentNode["body"])
                self.scopeManager.PopScope()

                if not self.Builder.block.is_terminated:
                    if endBlock == None: endBlock = self.Builder.append_basic_block()
                    self.Builder.branch(endBlock)

            currentNode = currentNode["else"] \
                if "else" in currentNode and currentNode["else"]["body"] else None
        
        if endBlock != None:
            self.Builder.position_at_end(endBlock)

    def VisitTypedef(self, node):
        self.scopeManager.Set(node["name"], self.VisitType(node["value"]), force = True)

    def VisitType(self, node, uuid = None):
        if isinstance(node, ir.Type) or node is None:
            return node
        
        if isinstance(node, str):
            node = {"type": "identifier", "value": node}
        
        if node["type"] == "identifier":
            assert self.scopeManager.Has(node["value"], uuid), f"Unknown type '{node["value"]}'."
            value = self.scopeManager.Get(node["value"], uuid)
            if isinstance(value, Class): value = value.type
            assert isinstance(value, ir.Type), "Expected a type."
            return value
        
        elif node["type"] == "call":
            value = self.VisitCall(node)
            if isinstance(value, Class): value = value.type
            assert isinstance(value, ir.Type), "Expected a type."
            return value

        elif node["type"] == "pointer":
            value = self.VisitType(node["value"], uuid)
            return ir.IntType(8).as_pointer() if isinstance(value, ir.VoidType) else value.as_pointer()
        
        elif node["type"] == "array":
            if node["size"]:
                return ir.ArrayType(self.VisitType(node["value"], uuid), node["size"])
            
            else:
                return self.VisitType(node["value"], uuid).as_pointer()
            
        elif node["type"] == "template":
            return self.scopeManager.Get(node["value"], uuid).Get(node["params"])
            
        elif node["type"] in ["const", "unsigned", "signed"]:
            return self.VisitType(node["value"], uuid)
        
        elif node["type"] == "function":
            assert "body" not in node, "Invalid type."
            return ir.FunctionType(self.VisitType(node["return"], uuid), [self.VisitType(i, uuid) for i in node["params"] if i not in ["three dot"]], "three dot" in node["params"]).as_pointer()
        
        else:
            assert False, f"Unknown type '{node["type"]}'."

    def VisitCast(self, node, force = True, test = False):
        value, target = self.VisitValue(node["value"]), self.VisitType(node["target"])

        if test:
            if isinstance(value.type, ir.ArrayType) and target.is_pointer and value.type.element == target.pointee: return True
            return self.VisitCast(node, force) != value

        if value.type.is_pointer:
            if isinstance(target, ir.IntType): return self.Builder.ptrtoint(value, target)
            else: ...

        elif isinstance(value.type, ir.FloatType):
            if isinstance(target, ir.IntType): return self.Builder.fptosi(value, target)
            if isinstance(target, ir.DoubleType): return self.Builder.fpext(value, target)
            if isinstance(target, ir.FloatType): return value

        elif isinstance(value.type, ir.DoubleType):
            if isinstance(target, ir.IntType): return self.Builder.fptosi(value, target)
            if isinstance(target, ir.FloatType): return self.Builder.fptrunc(value, target)
            if isinstance(target, ir.DoubleType): return value

        elif isinstance(value.type, ir.IntType):
            if target.is_pointer: return self.Builder.inttoptr(value, target)
            if isinstance(target, ir.FloatType) or isinstance(target, ir.DoubleType):
                return self.Builder.sitofp(value, target)
            
            if isinstance(target, ir.IntType):
                if target.width > value.type.width: return self.Builder.sext(value, target)
                else: return self.Builder.trunc(value, target)

        else:
            ...

        return self.Builder.bitcast(value, target) if force else value

    def VisitValue(self, node, uuid = None):
        if isinstance(node, ir.Value) or node is None:
            return node

        elif node["type"] in ["bool", "i8", "i16", "i32", "i64", "float", "double"] or isinstance(node["type"], dict):
            return ir.Constant(self.VisitType(node["type"], uuid), node["value"])

        elif node["type"] in ["identifier", "get", "get element", "get element pointer", "dereference"]:
            return self.Builder.load(self.VisitPointer(node, uuid))

        elif node["type"] in ["not", "bitwise not"]:
            return self.Builder.not_(self.VisitValue(node["value"], uuid))

        elif node["type"] == "initializer list":
            return [self.VisitValue(i, uuid) for i in node["body"]]

        elif node["type"] == "negate":
            value = self.VisitValue(node["value"], uuid)
            return getattr(self.Builder, "fneg" if isinstance(value.type, ir.FloatType) else "neg")(value)

        elif node["type"] == "expression":
            return self.VisitExpression(node)

        elif node["type"] == "cast":
            return self.VisitCast(node)

        elif node["type"] == "call":
            return self.VisitCall(node)

        elif node["type"] == "string":
            buffer = bytearray((node["value"] + "\0").encode("utf-8"))
            return ir.Constant(ir.ArrayType(ir.IntType(8), len(buffer)), buffer)

        elif node["type"] == "reference":
            return self.VisitPointer(node["value"], uuid)
        
        else:
            assert False, f"Unknown value '{node["type"]}'."

    def VisitPointer(self, node, uuid = None):
        if isinstance(node, ir.PointerType) or isinstance(node, ir.Instruction) or node is None:
            return node
        
        if node["type"] == "identifier":
            if self.scopeManager.Class is not None:
                if self.scopeManager.Class.Has(node["value"]):
                    element = self.scopeManager.Class.Get(node["value"]).copy()
                    value = self.Builder.load(self.scopeManager.Get("this", uuid))
                    assert value.type.is_pointer, "Expected a pointer."

                    if value.type.pointee == self.scopeManager.Class.type:
                        if isinstance(element["type"], ir.Function):
                            element["pointer"], element["access"] = value, "public"
                            return element
                        
                        return self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), self.scopeManager.Class.Index(node["value"]))])

            assert self.scopeManager.Has(node["value"], uuid), f"Unknown identifier '{node["value"]}'."
            return self.scopeManager.Get(node["value"], uuid)
        
        elif node["type"] == "get":
            return self.Builder.gep(self.VisitValue(node["value"], uuid), [self.VisitValue(node["index"], uuid)])
        
        elif node["type"] in ["get element", "get element pointer"]:
            value = {"get element pointer": self.VisitValue, "get element": self.VisitPointer}[node["type"]](node["value"], uuid)
            assert value.type.is_pointer, "Expected a pointer got a class."
            assert not value.type.pointee.is_pointer, "Expected a class got a pointer."
            assert isinstance(value.type.pointee, ir.BaseStructType), "Pointer must point a class."
            if self.scopeManager.Class and self.scopeManager.Class.Name == value.type.pointee.name: _class = self.scopeManager.Class
            else: _class = self.scopeManager.Get(value.type.pointee.name, uuid)
            assert _class.Has(node["element"]), f"Class '{value.type.pointee.name}' does not have element '{node["element"]}'."
            element = _class.Get(node["element"]).copy()
            assert not (element["access"] != "public" and _class != self.scopeManager.Class), "Access violation."

            if isinstance(element["type"], ir.Function):
                if self.scopeManager.Class == _class:
                    element["access"] = "public"

                element["pointer"] = value
                return element

            return self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(node["element"]))])
        
        elif node["type"] == "dereference":
            value = self.VisitValue(node["value"], uuid)
            assert value.type.is_pointer, "Expected a pointer."
            return value

        else:
            assert False, f"Unknown pointer '{node["type"]}'."

    def VisitConstructor(self, _class, ptr, params = []):
        for name, value in _class.Elements.items():
            if isinstance(value["type"], ir.BaseStructType):
                self.VisitConstructor(self.scopeManager.Get(value["type"].name), self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]))

            else:
                if not value["value"]: continue
                self.VisitAssign({"left": self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]), "right": value["value"]})

        if _class.Has(_class.Name):
            self.VisitCall({"value": {"type": "get element pointer", "value": ptr, "element": _class.Name}, "params": params})

    def VisitDestructor(self, _class, ptr):
        for name, value in _class.Elements.items():
            if isinstance(value["type"], ir.BaseStructType):
                self.VisitDestructor(self.scopeManager.Get(value["type"].name), self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]))

        if _class.Has(f"~{_class.Name}"):
            self.VisitCall({"value": {"type": "get element pointer", "value": ptr, "element": f"~{_class.Name}"}, "params": []})

    def VisitDefine(self, node):
        assert not self.scopeManager.Scope.Has(node["name"]), f"Redefinition of '{node["name"]}'."
        dataType = self.VisitType(node["dataType"])

        if node["value"]:
            value = self.VisitValue(node["value"])

            if not isinstance(value, list) and value.type != dataType:
                value = self.VisitCast({"value": value, "target": dataType}, force = False)

        if dataType.is_pointer and node["value"] and not isinstance(value, list) and isinstance(value.type, ir.ArrayType):
            dataType = ir.ArrayType(dataType.pointee, value.type.count)

        ptr = self.Builder.alloca(dataType)
        if node["value"] and not isinstance(value, list): self.Builder.store(value, ptr, self.scopeManager.Get("alignof")(value).constant)
        self.scopeManager.Set(node["name"], ptr, force = True)

        if not dataType.is_pointer and isinstance(dataType, ir.BaseStructType):
            self.VisitConstructor(self.scopeManager.Get(dataType.name), ptr, value if node["value"] and isinstance(value, list) else [])

    def VisitAssign(self, node):
        ptr = self.VisitPointer(node["left"])
        assert ptr.type.is_pointer, "Left side of an assignment must be a pointer."

        if isinstance(ptr.type.pointee, ir.BaseStructType):
            if node["right"]["type"] in ["expression"] and node["left"] in [node["right"]["left"], node["right"]["right"]] and self.scopeManager.Get(ptr.type.pointee.name).Has(f"operator{node['right']['operator']}="):
                return self.VisitCall({"value": {"type": "get element pointer", "value": ptr, "element": f"operator{node['right']['operator']}="}, "params": [ptr, self.VisitValue(node["right"]["right" if node["left"] == node["right"]["left"] else "left"])]})

        value = self.VisitValue(node["right"])

        if ptr.type.pointee != value.type:
            value = self.VisitCast({"value": value, "target": ptr.type.pointee}, force = False)

        if not value.type.is_pointer and isinstance(value.type, ir.ArrayType):
            _ptr = self.Builder.alloca(value.type)
            self.Builder.store(value, _ptr, self.scopeManager.Get("alignof")(value).constant)
            value = _ptr

        if value.type.is_pointer and isinstance(value.type.pointee, ir.ArrayType):
            value = self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])

        if isinstance(ptr.type.pointee, ir.BaseStructType):
            if self.scopeManager.Get(ptr.type.pointee.name).Has("operator="):
                return self.VisitCall({"value": {"type": "get element pointer", "value": ptr, "element": "operator="}, "params": [ptr, value]})

        self.Builder.store(value, ptr, self.scopeManager.Get("alignof")(value).constant)

    def VisitCall(self, node):
        func, args = self.VisitPointer(node["value"]), []
        highestScore = 0

        if not isinstance(func, list):
            func = [func]

        for index, i in enumerate(func):
            score = 1

            if isinstance(i, dict) and "access" in i:
                assert i["access"] == "public", "Access violation."
                if i["pointer"] not in node["params"]: node["params"] = [i["pointer"]] + node["params"]
                i = i["type"]

            else:
                if hasattr(i, "parent_struct") and i.parent_struct != self.scopeManager.Class:
                    assert i.parent_struct.Get(i.name)["access"] == "public", "Access violation."

            if isinstance(func, ir.Function):
                if len(node["params"]) < len(i.function_type.args) if i.function_type.var_arg else len(node["params"]) != len(i.function_type.args):
                    continue

                for index, j in enumerate(i.function_type.args):
                    value = self.VisitValue(node["params"][index])

                    if value.type == j:
                        score += 1

                    elif not self.VisitCast({"value": value, "target": j}, force = False, test = True):
                        score = 0
                        break

                    else:
                        ...
                    
            if score > highestScore:
                func, highestScore = i, score

        assert func is not None, "Invalid arguments."

        if isinstance(func, CompileTimeFunction):
            return func(*node["params"])

        for index, i in enumerate(node["params"]):
            value = self.VisitValue(i)

            if isinstance(func, ir.Function) and index < len(func.function_type.args) and value.type != func.function_type.args[index]:
                value = self.VisitCast({"value": value, "target": func.function_type.args[index]}, force = False)

            if not value.type.is_pointer and isinstance(value.type, ir.ArrayType):
                ptr = self.Builder.alloca(value.type)
                self.Builder.store(value, ptr, self.scopeManager.Get("alignof")(value).constant)
                value = ptr

            if value.type.is_pointer and isinstance(value.type.pointee, ir.ArrayType):
                value = self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])

            args.append(value)

        return self.Builder.call(func, args)
    
    def VisitFor(self, node):
        forBlock = self.Builder.append_basic_block()
        endBlock = self.Builder.append_basic_block()

        if node["declaration"]:
            self.Compile(node["declaration"])

        if not node["condition"]:
            self.Builder.branch(forBlock)

        else:
            condition = self.VisitValue(node["condition"])
            self.Builder.cbranch(condition, forBlock, endBlock)

        self.Builder.position_at_start(forBlock)
        self.scopeManager.PushScope(Scope(node["type"]))
        self.Compile(node["body"])
        self.scopeManager.PopScope()

        if not self.Builder.block.is_terminated:
            if node["iteration"]:
                self.Compile(node["iteration"])

            if not node["condition"]:
                self.Builder.branch(forBlock)

            else:
                condition = self.VisitValue(node["condition"])
                self.Builder.cbranch(condition, forBlock, endBlock)

        self.Builder.position_at_start(endBlock)
    
    def VisitWhile(self, node):
        condition = self.VisitValue(node["condition"])
        whileBlock = self.Builder.append_basic_block()

        if node["else"]["body"]:
            elseBlock = self.Builder.append_basic_block()

        endBlock = self.Builder.append_basic_block()
        self.Builder.cbranch(condition, whileBlock, elseBlock if node["else"]["body"] else endBlock)
        self.Builder.position_at_start(whileBlock)
        self.scopeManager.PushScope(Scope(node["type"]))
        self.Compile(node["body"])
        self.scopeManager.PopScope()

        if not self.Builder.block.is_terminated:
            condition = self.VisitValue(node["condition"])
            self.Builder.cbranch(condition, whileBlock, endBlock)

        if node["else"]["body"]:
            self.Builder.position_at_start(elseBlock)
            self.scopeManager.PushScope(Scope("else"))
            self.Compile(node["else"]["body"])
            self.scopeManager.PopScope()

            if not self.Builder.block.is_terminated:
                self.Builder.branch(endBlock)

        self.Builder.position_at_start(endBlock)

    def VisitReturn(self, node):
        self.InvokeDestructors()

        if node["value"]:
            value = self.VisitValue(node["value"])

            if not value.type.is_pointer and isinstance(value.type, ir.ArrayType):
                ptr = self.Builder.alloca(value.type)
                self.Builder.store(value, ptr, self.scopeManager.Get("alignof")(value).constant)
                value = ptr

            if value.type.is_pointer and isinstance(value.type.pointee, ir.ArrayType):
                value = self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])

            self.Builder.ret(value)

        else:
            self.Builder.ret_void()

    def VisitExpression(self, node):
        if "body" in node:
            for i in node["body"]:
                self.Compile([i])

            return
        
        left = self.VisitValue(node["left"])
        right = self.VisitValue(node["right"])

        if left.type.is_pointer or right.type.is_pointer:
            if left.type.is_pointer: left = self.VisitCast({"value": left, "target": ir.IntType(64)})
            if right.type.is_pointer: right = self.VisitCast({"value": right, "target": ir.IntType(64)})

        if isinstance(left.type, ir.FloatType) or isinstance(right.type, ir.FloatType) or isinstance(left.type, ir.DoubleType) or isinstance(right.type, ir.DoubleType):
            # type = ir.DoubleType if isinstance(left.type, ir.DoubleType) or isinstance(right.type, ir.DoubleType) else ir.FloatType
            if not isinstance(left.type, ir.FloatType): left = self.VisitCast({"value": left, "target": ir.FloatType()})
            if not isinstance(right.type, ir.FloatType): right = self.VisitCast({"value": right, "target": ir.FloatType()})

            if node["operator"] == "+":
                return self.Builder.fadd(left, right)

            elif node["operator"] == "*":
                return self.Builder.fmul(left, right)

            elif node["operator"] == "/":
                return self.Builder.fdiv(left, right)

            elif node["operator"] == "%":
                return self.Builder.frem(left, right)

            elif node["operator"] == "-":
                return self.Builder.fsub(left, right)

            elif node["operator"] in ["<", "<=", ">", ">=", "!=", "=="]:
                return self.Builder.fcmp_ordered(node["operator"], left, right)

            else:
                assert False, f"Invalid operator '{node["operator"]}'."
        
        elif isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType):
            if node["operator"] in ["&&", "||"]:
                if left.type.width != 1: left = self.VisitExpression({"operator": ">", "left": left, "right": ir.Constant(ir.IntType(left.type.width), 0)})
                if right.type.width != 1: right = self.VisitExpression({"operator": ">", "left": right, "right": ir.Constant(ir.IntType(right.type.width), 0)})

            if left.type.width != right.type.width:
                left = self.VisitCast({"value": left, "target": ir.IntType(max(left.type.width, right.type.width))})
                right = self.VisitCast({"value": right, "target": ir.IntType(max(left.type.width, right.type.width))})

            if node["operator"] == "+":
                return self.Builder.add(left, right)

            elif node["operator"] == "*":
                return self.Builder.mul(left, right)

            elif node["operator"] == "/":
                return self.Builder.sdiv(left, right)

            elif node["operator"] == "%":
                return self.Builder.srem(left, right)

            elif node["operator"] == "-":
                return self.Builder.sub(left, right)

            elif node["operator"] in ["<", "<=", ">", ">=", "!=", "=="]:
                return self.Builder.icmp_signed(node["operator"], left, right)

            elif node["operator"] in ["&", "&&"]:
                return self.Builder.and_(left, right)

            elif node["operator"] in ["|", "||"]:
                return self.Builder.or_(left, right)

            elif node["operator"] == "^":
                return self.Builder.xor(left, right)

            elif node["operator"] == ">>":
                return self.Builder.ashr(left, right)

            elif node["operator"] == "<<":
                return self.Builder.shl(left, right)

            else:
                assert False, f"Invalid operator '{node["operator"]}'."
            
        else:
            assert False, "Invalid expression."