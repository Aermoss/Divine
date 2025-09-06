import os, sys, copy

from llvmlite import ir

from lexer import Lexer
from parser import Parser

class Scope:
    def __init__(self, namespace = None, local = False):
        self.variables, self.children, self.parent = {}, [], None
        self.local, self.namespace = local, namespace

    def Has(self, name):
        if name in self.variables:
            return True

        for _name in self.variables:
            if not Mangler.IsMangled(_name): continue
            if Mangler.Demangle(_name)[0] in [name]:
                return True

        return False

    def Set(self, name, value):
        self.variables[name] = value

    def Get(self, name):
        if name in self.variables:
            return self.variables[name]

        matches = []

        for _name in self.variables:
            if not Mangler.IsMangled(_name): continue
            if Mangler.Demangle(_name)[0] in [name]:
                matches.append(self.variables[_name])

        assert matches, f"Unknown variable '{name}'."
        return matches if len(matches) > 1 else matches[0]

class ScopeManager:
    def __init__(self):
        self.__scope = self.__global = Scope()
        self.__class = None

    @property
    def Global(self):
        return self.__global

    @property
    def Scope(self):
        return self.__scope

    def PushScope(self, scope):
        self.__scope.children.append(scope)
        self.__scope, scope.parent = scope, self.__scope

    def PopScope(self):
        assert self.__scope.parent is not None, "No scope to pop."

        if self.__scope.local:
            self.__scope.parent.children.remove(self.__scope)
            self.__scope.parent, self.__scope = None, self.__scope.parent

        else:
            self.__scope = self.__scope.parent

    @property
    def Class(self):
        return self.__class

    def PushClass(self, _class):
        assert self.__class is None, "Already in a class."
        self.__class = _class

    def PopClass(self):
        assert self.__class is not None, "No class to pop."
        self.__class = None

    @property
    def Namespaces(self):
        return self.NamespacesByScope(self.__scope)

    @property
    def Namespace(self):
        return "::".join(self.Namespaces)

    def NamespacesByScope(self, scope, demangle = True):
        while scope.local:
            scope = scope.parent

        namespaces = []

        while scope.parent is not None:
            namespaces.append(Mangler.Demangle(scope.namespace)[0] if demangle else scope.namespace)
            scope = scope.parent

        return namespaces

    def ScopeByNamespaces(self, namespaces):
        scope, state = self.__scope, False

        while scope.local:
            scope = scope.parent

        for index, namespace in enumerate(namespaces):
            found = False

            if namespace == "":
                assert index == 0, "Invalid namespace."
                scope = self.__global
                continue

            while not found:
                for child in scope.children:
                    if child.namespace and Mangler.Demangle(child.namespace)[0] in [namespace]:
                        scope, state, found = child, True, True
                        break

                if not found and not state and scope.parent is not None:
                    scope = scope.parent

                else:
                    break

            assert found, f"Unknown namespace: '{namespace}'."

        return scope

    def Has(self, name):
        if Mangler.IsMangled(name):
            _, namespaces = Mangler.Demangle(name)

        else:
            names = name.split("::")
            name, namespaces = names[-1], names[:-1]

        if namespaces:
            return self.ScopeByNamespaces(namespaces).Has(name)

        else:
            scope = self.__scope

            while scope is not None:
                if scope.Has(name):
                    return True

                scope = scope.parent

            return False

    def Set(self, name, value):
        if Mangler.IsMangled(name):
            _, namespaces = Mangler.Demangle(name)
            assert namespaces == self.NamespacesByScope(self.__scope), "Mangle namespace mismatch."

        else:
            names = name.split("::")
            name, namespaces = names[-1], names[:-1]
            assert not namespaces, "Namespace not allowed."

        self.__scope.Set(name, value)

    def Get(self, name):
        if Mangler.IsMangled(name):
            _, namespaces = Mangler.Demangle(name)

        else:
            names = name.split("::")
            name, namespaces = names[-1], names[:-1]

        if namespaces:
            scope = self.ScopeByNamespaces(namespaces)
            assert scope.Has(name), f"Unknown variable: '{name}'"
            return scope.Get(name)

        else:
            scope = self.__scope

            while scope is not None:
                if scope.Has(name):
                    return scope.Get(name)

                scope = scope.parent

            assert False, f"Unknown variable: '{name}'"

class Class:
    def __init__(self, compiler, name, realName):
        self.__compiler, self.__name, self.__realName = compiler, name, realName
        self.type = ir.global_context.get_identified_type(name)
        self.__elements, self.__functions = {}, {}

    @property
    def Name(self):
        return self.__name

    @property
    def RealName(self):
        return self.__realName

    @property
    def Elements(self):
        return self.__elements.copy()
    
    @property
    def Functions(self):
        return self.__functions.copy()

    def Cook(self):
        if self.type.elements is not None: return
        sizeof, alignof = self.__compiler.sizeof, self.__compiler.alignof
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
                    elements[f"<p@{offset}:{padding}>"] = {"type": ir.ArrayType(ir.IntType(8), padding), "value": None, "access": None}
                    offset += padding

            if i is not None:
                elements[i] = self.__elements[i]
                offset += size

        self.__elements = elements.copy()
        self.type.set_body(*[i["type"] for i in self.__elements.values()])
        return self

    def RegisterElement(self, name, value):
        self.__elements[name] = value

    def RegisterFunction(self, name, value):
        self.__functions[name] = value

    def Index(self, name):
        return list(self.__elements.keys()).index(name)

    def Has(self, name):
        if name in self.__elements or name in self.__functions:
            return True

        for _name in self.__functions:
            if not Mangler.IsMangled(_name): continue
            if Mangler.Demangle(_name)[0] in [name]:
                return True

        return False

    def Get(self, name):
        if name in self.__elements:
            return self.__elements[name]

        if name in self.__functions:
            return self.__functions[name]

        matches = []

        for _name in self.__functions:
            if not Mangler.IsMangled(_name): continue
            if Mangler.Demangle(_name)[0] in [name]:
                matches.append(self.__functions[_name])

        assert matches, f"Unknown variable '{name}'."
        return matches if len(matches) > 1 else matches[0]

class Template:
    def __init__(self, compiler, scope, body, params):
        self.__compiler, self.__scope = compiler, scope
        self.__body, self.__params = body, params
        self.__instances = {}

    def Get(self, params):
        assert len(self.__params) == len(params), "Parameter count mismatch."
        params = tuple(self.__compiler.VisitType(param) for param in params)

        if params in self.__instances:
            return self.__instances[params]

        scope, self.__compiler.scopeManager._ScopeManager__scope = \
            self.__compiler.scopeManager._ScopeManager__scope, self.__scope

        for index, i in enumerate(self.__params):
            self.__scope.Set(i["name"], params[index])

        body = copy.deepcopy(self.__body)
        body["name"], body["_name"] = Mangler.MangleClass(body["name"], params), body["name"]
        mangling, self.__compiler.mangling = self.__compiler.mangling, True
        _currentClass = self.__compiler.scopeManager.Class

        if self.__compiler.scopeManager.Class:
            self.__compiler.scopeManager.PopClass()

        self.__compiler.Compile([body])

        if _currentClass:
            self.__compiler.scopeManager.PushClass(_currentClass)

        self.__compiler.mangling = mangling
        _class = self.__compiler.scopeManager.Get(body["name"])
        self.__instances[params] = _class.type

        for index, i in enumerate(self.__params):
            del self.__scope.variables[i["name"]]

        self.__compiler.scopeManager._ScopeManager__scope = scope
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
            return ir.Constant(ir.IntType(64), type.count * self(type.element).constant)

        elif isinstance(type, ir.BaseStructType):
            return ir.Constant(ir.IntType(64), sum([self(i).constant for i in type.elements]))

        elif isinstance(type, ir.PointerType):
            return ir.Constant(ir.IntType(64), 8)

        elif isinstance(type, ir.IntType):
            return ir.Constant(ir.IntType(64), max(type.width // 8, 1))

        elif isinstance(type, ir.FloatType):
            return ir.Constant(ir.IntType(64), 4)

        elif isinstance(type, ir.DoubleType):
            return ir.Constant(ir.IntType(64), 8)

        else:
            assert False, f"Unknown type: '{type}'."

class AlignOf(CompileTimeFunction):
    def __init__(self, compiler):
        super().__init__(compiler)

    def __call__(self, value):
        try:
            type = self.compiler.VisitType(value)

        except:
            type = self.compiler.VisitValue(value).type

        if isinstance(type, ir.ArrayType):
            return ir.Constant(ir.IntType(64), self(type.element).constant)

        elif isinstance(type, ir.BaseStructType):
            return ir.Constant(ir.IntType(64), max([self(i).constant for i in type.elements]))

        elif isinstance(type, ir.PointerType):
            return ir.Constant(ir.IntType(64), 8)

        elif isinstance(type, ir.IntType):
            return ir.Constant(ir.IntType(64), max(type.width // 8, 1))

        elif isinstance(type, ir.FloatType):
            return ir.Constant(ir.IntType(64), 4)

        elif isinstance(type, ir.DoubleType):
            return ir.Constant(ir.IntType(64), 8)

        else:
            assert False, f"Unknown type: '{type}'."

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
        return ir.Constant(ir.IntType(64), sum([sizeof(i).constant for i in type.elements[:_class.Index(element["value"])]]))

class DeclType(CompileTimeFunction):
    def __init__(self, compiler):
        super().__init__(compiler)

    def __call__(self, value):
        return self.compiler.VisitValue(value).type

class Mangler:
    prefix = "$d"

    @classmethod
    def MangleName(cls, name):
        return f"{len(name)}{name}"

    @classmethod
    def MangleNestedName(cls, names, extra = ""):
        return f"N{"".join((name[len(cls.prefix):] if cls.IsMangled(name) else cls.MangleName(name)) for name in names)}{extra}E"

    @classmethod
    def MangleTemplate(cls, name, types):
        return f"{cls.MangleName(name)}I{"".join(cls.MangleType(type) for type in types)}E"

    @classmethod
    def MangleType(cls, type):
        if isinstance(type, ir.VoidType):
            return "v"

        elif isinstance(type, ir.DoubleType):
            return "d"

        elif isinstance(type, ir.FloatType):
            return "f"

        elif isinstance(type, ir.IntType):
            return {1: "b", 8: "c", 16: "s", 32: "i", 64: "l"}[type.width]

        elif isinstance(type, ir.PointerType):
            if type.is_opaque:
                return "Pv"

            else:
                return f"P{cls.MangleType(type.pointee)}"

        elif isinstance(type, ir.BaseStructType):
            return type.name[len(cls.prefix):] if cls.IsMangled(type.name) else cls.MangleName(type.name)

        elif isinstance(type, ir.FunctionType):
            return f"F{"".join(cls.MangleType(type) for type in [type.return_type] + list(type.args))}E"

        else:
            assert False, f"Unknown type: '{type}'."

    @classmethod
    def MangleFunction(cls, name, types, namespaces = []):
        return f"{cls.prefix}{cls.MangleNestedName(namespaces + [name]) if namespaces else cls.MangleName(name)}{"".join(cls.MangleType(type) for type in types)}"

    @classmethod
    def MangleClass(cls, name, types, namespaces = []):
        name = cls.MangleTemplate(name, types) if types else cls.MangleName(name)
        return f"{cls.prefix}{cls.MangleNestedName(namespaces, name) if namespaces else name}"

    @classmethod
    def MangleString(cls, string):
        return f"{cls.prefix}@{"".join(i if i.isalnum() else "?" for i in string)}@{hash(string.encode()) % ((sys.maxsize + 1) * 2):x}"

    @classmethod
    def IsMangled(cls, name):
        return name.startswith(cls.prefix)

    @classmethod
    def Demangle(cls, mangle):
        if not cls.IsMangled(mangle): return mangle, []
        names, depth, index = [], 0, len(cls.prefix)

        while len(mangle) > index:
            digit = ""

            if mangle[index] in ["I"]:
                ignore = 0

                while len(mangle) > index:
                    names[-1] += mangle[index]

                    if mangle[index] in ["I", "F"]:
                        ignore += 1

                    elif mangle[index] in ["E"]:
                        ignore -= 1

                        if not ignore:
                            break

                    while mangle[index].isdigit():
                        index += 1

                    else:
                        index += 1

                if not depth:
                    break

            elif mangle[index] in ["N", "F"]:
                depth += 1

            elif mangle[index] in ["E"]:
                depth -= 1

                if not depth:
                    break

            while mangle[index].isdigit():
                digit += mangle[index]
                index += 1

            if digit:
                names.append(mangle[index:index + int(digit)])
                index += int(digit)

                if not depth and len(mangle) > index and mangle[index] not in ["I"]:
                    break

            else:
                index += 1

        return names[-1], names[:-1]

def Timer(func):
    import time

    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        color = "\033[92m" if duration < 0.0001 else "\033[93m" if duration < 1 else "\033[91m"
        if color in ["\033[91m"]: print(f"[TIMER] '{func.__name__}' took {color}{duration:.6f}\033[0m seconds.")
        return result

    return wrapper

class Compiler:
    def __init__(self):
        self.module = ir.Module("main")
        self.scopeManager = ScopeManager()
        self.primitiveTypes = {
            "void": ir.VoidType(), "bool": ir.IntType(1), "char": ir.IntType(32),
            "i8": ir.IntType(8), "i16": ir.IntType(16), "i32": ir.IntType(32), "i64": ir.IntType(64), "i128": ir.IntType(128),
            "u8": ir.IntType(8), "u16": ir.IntType(16), "u32": ir.IntType(32), "u64": ir.IntType(64), "u128": ir.IntType(128),
            "f32": ir.FloatType(), "f64": ir.DoubleType()
        }

        for name, type in self.primitiveTypes.items():
            self.scopeManager.Set(name, type)

        self.scopeManager.Set("sizeof", sizeof := SizeOf(self))
        self.scopeManager.Set("alignof", alignof := AlignOf(self))
        self.scopeManager.Set("offsetof", offsetof := OffsetOf(self))
        self.sizeof, self.alignof, self.offsetof = sizeof, alignof, offsetof
        self.scopeManager.Set("decltype", DeclType(self))
        self.memcpy = ir.Function(self.module, ir.FunctionType(ir.VoidType(), [ir.PointerType(), ir.PointerType(), ir.IntType(64), ir.IntType(1)]), "llvm.memcpy.p0.p0.i64")
        self.includePaths, self.entryPoints = [], ["main", "WinMain", "DllMain"]
        self.stringCache, self.builderStack, self.mangling = {}, [], True
        self.__includedFiles = []

    @property
    def Builder(self) -> ir.builder.IRBuilder:
        if len(self.builderStack) < 1: return None
        return self.builderStack[-1]

    def PushBuilder(self, builder):
        self.builderStack.append(builder)

    def PopBuilder(self):
        assert len(self.builderStack) > 0, "No builder to pop."
        return self.builderStack.pop()

    def PushBlockState(self):
        if not hasattr(self.Builder._block, "_stateStack"): self.Builder._block._stateStack = []
        self.Builder._block._stateStack.append((self.Builder._block.instructions.copy(), self.Builder._anchor))

    def PopBlockState(self):
        assert hasattr(self.Builder._block, "_stateStack") and len(self.Builder._block._stateStack) > 0, "No block state to pop."
        self.Builder._block.instructions, self.Builder._anchor = self.Builder._block._stateStack.pop()
        return (self.Builder._block.instructions, self.Builder._anchor)

    def InvokeDestructors(self, _except = None):
        for name, value in self.scopeManager.Scope.variables.items():
            if name in ["this"]:
                continue

            if hasattr(value, "type") and value.type.is_pointer and not value.type.is_opaque and isinstance(value.type.pointee, ir.BaseStructType):
                if value is not _except:
                    self.VisitDestructor(self.scopeManager.Get(value.type.pointee.name), value)

    def Compile(self, ast):
        for node in ast:
            if node is None: continue
            if self.Builder is not None and self.Builder.block.is_terminated: break
            name = f"Visit{"".join([i.capitalize() for i in node["type"].split(" ")])}"
            assert hasattr(self, name), f"Unknown node '{node["type"]}'."
            getattr(self, name)(node)

        return self.module

    def TryPack(self, return_, arguments):
        _return, names, types = ir.VoidType(), [], []

        for index, (name, type) in enumerate([(None, return_)] + arguments):
            if isinstance(type, ir.BaseStructType):
                if (size := self.sizeof(type).constant) > 8:
                    new = type.as_pointer()
                    if index != 0: new._byval, type = type, new
                    else: new._sret, type = type, new
                    names.append(name)
                    types.append(type)
                    continue

                else:
                    _instance_cache, ir.IntType._instance_cache = \
                        ir.IntType._instance_cache, {}

                    if size > 4: new = ir.IntType(64)
                    elif size > 2: new = ir.IntType(32)
                    elif size > 1: new = ir.IntType(16)
                    else: new = ir.IntType(8)

                    ir.IntType._instance_cache = {} # _instance_cache

                    if index != 0:
                        new._byval, type = type, new

                    else:
                        new._sret, type = type, new

            if index != 0:
                names.append(name)
                types.append(type)

            else:
                _return = type

        return _return, tuple(names), tuple(types)

    def TryPass(self, value, _return = False):
        if not value.type.is_pointer and isinstance(value.type, ir.ArrayType) and not _return:
            current = self.Builder.block
            self.Builder.position_at_start(self.Builder.function.entry_basic_block)
            ptr = self.Builder.alloca(value.type)
            self.Builder.store(value, ptr, self.alignof(value).constant)
            self.Builder.position_at_end(current)
            value = ptr

        if value.type.is_pointer and not value.type.is_opaque and isinstance(value.type.pointee, ir.ArrayType):
            value = self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])

        return value

    @Timer
    def VisitConstExpr(self, node):
        if isinstance(node, ir.Constant):
            return node

        if node["type"] in ["expression"]:
            left, right = self.VisitConstExpr(node["left"]), self.VisitConstExpr(node["right"])

            if isinstance(left.type, ir.DoubleType) or isinstance(right.type, ir.DoubleType):
                type = ir.DoubleType()

            elif isinstance(left.type, ir.FloatType) or isinstance(right.type, ir.FloatType):
                type = ir.FloatType()

            elif isinstance(left.type, ir.IntType) or isinstance(right.type, ir.IntType):
                type = ir.IntType(max(left.type.width, right.type.width))

            else:
                assert False, f"Unknown type: '{left.type}' and/or '{right.type}'."

            if left.type != type: left = ir.Constant(type, left.constant)
            if right.type != type: right = ir.Constant(type, right.constant)

            assert node["operator"] not in ["&", "|", "^", ">>", "<<"] or isinstance(type, ir.IntType), "Bitwise operations can only be performed on integers."
            assert node["operator"] not in ["&&", "||"] or (isinstance(type, ir.IntType) and type.width == 1), "Logical operations can only be performed on booleans."
            return ir.Constant(ir.IntType(1) if node["operator"] in ["<", "<=", ">", ">=", "!=", "=="] else (ir.FloatType() if node["operator"] in ["/", "%"] and not (isinstance(type, ir.FloatType) or isinstance(type, ir.DoubleType)) else type), eval(f"left.constant {node["operator"]} right.constant"))

        elif node["type"] in self.primitiveTypes:
            return ir.Constant(self.VisitType(node["type"]), node["value"])

        elif node["type"] in ["identifier"]:
            value = self.VisitPointer(node)
            assert not value.type.is_pointer, "Expected a constant."
            return value

        elif node["type"] in ["cast"]:
            value, target = self.VisitConstExpr(node["value"]), self.VisitType(node["target"])

            if isinstance(target, ir.IntType):
                if target.width == 1:
                    return ir.Constant(target, bool(value.constant))

                else:
                    return ir.Constant(target, int(value.constant))
                
            elif isinstance(target, ir.FloatType) or isinstance(target, ir.DoubleType):
                return ir.Constant(target, float(value.constant))
            
            else:
                assert False, f"Unknown type: '{target}'."

        elif node["type"] in ["negate"]:
            value = self.VisitConstExpr(node["value"])
            assert isinstance(value.type, ir.IntType) or isinstance(value.type, ir.FloatType) or isinstance(value.type, ir.DoubleType), \
                f"Expected an integer or float, got {value.type}."
            return ir.Constant(value.type, -value.constant)

        else:
            assert False, f"Unknown expression: '{node["type"]}'"

    @Timer
    def VisitEnum(self, node):
        assert not self.scopeManager.Scope.local, "Enums must be defined in global scope."
        type = ir.IntType(32) if node["dataType"] is None else self.VisitType(node["dataType"])
        assert isinstance(type, ir.IntType), f"Expected an integer type."
        self.scopeManager.Set(node["name"], type)
        self.scopeManager.PushScope(Scope(node["name"]))
        value = ir.Constant(type, 0)

        for i in node["body"]:
            if i["value"]:
                value = self.VisitConstExpr(i["value"])
                assert value.type == type, f"Expected an integer, got {value.type}."

            else:
                value = ir.Constant(type, value.constant + 1)

            self.scopeManager.Set(i["name"], value)

        self.scopeManager.PopScope()

    @Timer
    def VisitExtern(self, node):
        assert not self.scopeManager.Scope.local, "Extern blocks must be defined in global scope."
        assert self.mangling, "Cannot define extern blocks inside an extern block."
        assert node["linkage"] in ["C"], f"Invalid linkage type: '{node["linkage"]}'"

        self.mangling = False
        self.Compile(node["body"])
        self.mangling = True

    @Timer
    def VisitTemplate(self, node):
        assert not self.scopeManager.Scope.local, "Templates must be defined in global scope."
        assert node["body"]["type"] in ["class", "func"], "Expected a function or a class."
        self.scopeManager.Set(node["body"]["name"], Template(self, self.scopeManager.Scope, node["body"], node["params"]))

    @Timer
    def VisitClass(self, node):
        assert not self.scopeManager.Scope.local, "Classes must be defined in global scope."
        impl, name = [], node.get("_name", node["name"])
        self.scopeManager.PushClass(Class(self, node["name"], name))
        self.scopeManager.PushScope(Scope(node["name"]))

        for _name, member in node["members"].items():
            self.scopeManager.Class.RegisterElement(_name, {"type": self.VisitType(member["dataType"]), "value": self.VisitValue(member["value"]), "access": "private" if member["private"] else "public"})

        self.scopeManager.Scope.parent.Set(node["name"], self.scopeManager.Class.Cook())

        for i in node["impl"]:
            i = copy.deepcopy(i)

            if i["type"] in ["constructor", "destructor"]:
                i = {"type": "func", "return": "void", "name": f"~{name}" if i["type"] != "constructor" else name, "params": i["params"], "body": i["body"], "private": False}

            if i["type"] in ["operator"]:
                i = {"type": "func", "return": i["return"], "name": f"op{i['operator']}", "params": i["params"], "body": i["body"], "private": i["private"]}

            assert i["type"] == "func", f"Invalid implementation type: '{i["type"]}'."
            i["params"] = [{"type": self.scopeManager.Class.type.as_pointer(), "name": "this"}] + i["params"]
            self.scopeManager.Class.RegisterFunction(i["name"], {"type": self.VisitFunc(i, body = False), "access": "private" if i["private"] else "public"})
            impl.append(i)

        for i in impl:
            func = self.VisitFunc(i, override = True)
            self.scopeManager.Class.RegisterFunction(i["name"], {"type": func, "access": "private" if i["private"] else "public"})
            self.scopeManager.Set(i["name"], func)

        self.scopeManager.PopScope()
        self.scopeManager.PopClass()

    @Timer
    def VisitInclude(self, node):
        assert not self.scopeManager.Scope.local, "Includes must be made in global scope."

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
                        path = os.path.join(path, "entry.div")
                        assert os.path.exists(path), "Module entry point not found."
                        if path in self.__includedFiles: return
                        else: self.__includedFiles.append(path)
                        source = open(path, "r").read()
                        break

            lexer, parser = Lexer(), Parser()
            assert source is not None, f"Module '{i}' not found."
            parser.parse(lexer.tokenize(source))

            if node["namespace"]:
                self.scopeManager.PushNamespace(i.split(".")[0])

            self.Compile(parser.ast["body"])

            if node["namespace"]:
                self.scopeManager.PopNamespace()

    @Timer
    def VisitNamespace(self, node):
        assert not self.scopeManager.Scope.local, "Namespaces must be defined in global scope."
        self.scopeManager.PushNamespace(node["name"])
        self.Compile(node["body"])
        self.scopeManager.PopNamespace()

    @Timer
    def VisitFunc(self, node, body = True, override = False):
        assert not self.scopeManager.Scope.local, "Functions must be defined in global scope."
        arguments, threeDots, classState = [], False, False
        names = node["name"].split("::")
        namespaces, name = names[:-1], names[-1]

        if not self.scopeManager.Class:
            if namespaces and self.scopeManager.Has(namespaces[-1]):
                _class = self.scopeManager.Get(namespaces[-1])
                
                if isinstance(_class, Class):
                    assert _class.Has(name), f"Class '{namespaces[-1]}' does not have function '{name}'."
                    node["params"] = [{"type": _class.type.as_pointer(), "name": "this"}] + node["params"]
                    self.scopeManager.PushClass(_class)
                    classState = True

        for index, param in enumerate(node["params"]):
            if param["type"] != "three dot":
                arguments += [(param["name"], self.VisitType(param["type"]))]

            else:
                assert index == len(node["params"]) - 1, "Three dots must be the last parameter."
                threeDots = True

        _return, names, types = self.TryPack(self.VisitType(node["return"]), arguments)

        if not Mangler.IsMangled(name) and name not in self.entryPoints and self.mangling:
            name = Mangler.MangleFunction(name, types, namespaces = self.scopeManager.NamespacesByScope(self.scopeManager.ScopeByNamespaces(namespaces), demangle = False))

        if not self.scopeManager.Has(name):
            func = ir.Function(self.module, ir.FunctionType(_return, types, threeDots), name)

            for argument in func.args:
                if isinstance(argument.type, ir.PointerType):
                    if hasattr(argument.type, "_byval"):
                        argument.attributes.add("byval")

                    if hasattr(argument.type, "_sret"):
                        argument.attributes.add("sret")

            if self.scopeManager.Class: func._parentClass = self.scopeManager.Class
            self.scopeManager.Set(name, func)

        else:
            func = self.scopeManager.Get(name)
            assert not (not override and func.blocks), f"Function '{name}' already defined."

        if node["body"] and body:
            self.PushBuilder(ir.IRBuilder(func.append_basic_block()))
            self.scopeManager.PushScope(Scope(local = True))

            for index, (name, type) in enumerate(zip(names, types)):
                if hasattr(func.args[index].type, "_byval"):
                    current = self.Builder.block
                    self.Builder.position_at_start(self.Builder.function.entry_basic_block)
                    ptr = self.Builder.alloca(func.args[index].type._byval)
                    self.Builder.position_at_end(current)

                    if isinstance(func.args[index].type, ir.PointerType):
                        self.Builder.call(self.memcpy, [ptr, func.args[index], self.sizeof(func.args[index].type._byval), ir.Constant(ir.IntType(1), 0)])

                    else:
                        self.Builder.store(func.args[index], self.Builder.bitcast(ptr, func.args[index].type.as_pointer()), self.alignof(func.args[index]).constant)

                    self.scopeManager.Set(name, ptr)

                elif hasattr(func.args[index].type, "_sret"):
                    func.return_value.type._sret = type

                else:
                    current = self.Builder.block
                    self.Builder.position_at_start(self.Builder.function.entry_basic_block)
                    ptr = self.Builder.alloca(type)
                    self.Builder.position_at_end(current)
                    self.Builder.store(func.args[index], ptr, self.alignof(func.args[index]).constant)
                    self.scopeManager.Set(name, ptr)

            self.Compile(node["body"])

            if not self.Builder.block.is_terminated:
                assert func.return_value.type == ir.VoidType(), f"Function '{node["name"]}' must return a value."
                self.Builder.ret_void()

            self.scopeManager.PopScope()
            self.PopBuilder()

        if classState:
            self.scopeManager.PopClass()

        return func

    @Timer
    def VisitIf(self, node):
        assert self.scopeManager.Scope.local, "If blocks must be defined in local scope."
        endBlock, currentNode = None, node

        while currentNode:
            if "type" in currentNode:
                intermediateCheck = self.Builder.append_basic_block()
                ifBlock = self.Builder.append_basic_block()
                condition = self.VisitValue(currentNode["condition"])
                self.Builder.cbranch(condition, ifBlock, intermediateCheck)
                self.Builder.position_at_end(ifBlock)

                self.scopeManager.PushScope(Scope(local = True))
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

                self.scopeManager.PushScope(Scope(local = True))
                self.Compile(currentNode["body"])
                self.scopeManager.PopScope()

                if not self.Builder.block.is_terminated:
                    if not currentNode["else"]["body"]: endBlock = intermediateCheck
                    if endBlock == None: endBlock = self.Builder.append_basic_block()
                    self.Builder.branch(endBlock)

                self.Builder.position_at_end(intermediateCheck)

            else:
                self.scopeManager.PushScope(Scope(local = True))
                self.Compile(currentNode["body"])
                self.scopeManager.PopScope()

                if not self.Builder.block.is_terminated:
                    if endBlock == None: endBlock = self.Builder.append_basic_block()
                    self.Builder.branch(endBlock)

            currentNode = currentNode["else"] \
                if "else" in currentNode and currentNode["else"]["body"] else None
        
        if endBlock != None:
            self.Builder.position_at_end(endBlock)

    @Timer
    def VisitTypedef(self, node):
        assert not self.scopeManager.Scope.local, "Types must be defined in global scope."
        self.scopeManager.Set(node["name"], self.VisitType(node["value"]))

    @Timer
    def VisitType(self, node):
        if isinstance(node, str):
            node = {"type": "identifier", "value": node}

        if isinstance(node, ir.Type) or node is None:
            return node

        elif node["type"] == "identifier":
            assert self.scopeManager.Has(node["value"]), f"Unknown type '{node["value"]}'."
            value = self.scopeManager.Get(node["value"])
            if isinstance(value, Class): value = value.type
            assert isinstance(value, ir.Type), "Expected a type."
            return value

        elif node["type"] == "call":
            value = self.VisitCall(node)
            if isinstance(value, Class): value = value.type
            assert isinstance(value, ir.Type), "Expected a type."
            return value

        elif node["type"] == "pointer":
            value = self.VisitType(node["value"])
            return ir.PointerType() if isinstance(value, ir.VoidType) else value.as_pointer()

        elif node["type"] == "array":
            if node["size"]:
                return ir.ArrayType(self.VisitType(node["value"]), node["size"])
            
            else:
                return self.VisitType(node["value"]).as_pointer()

        elif node["type"] == "template":
            return self.scopeManager.Get(node["value"]).Get(node["params"])

        elif node["type"] == "function":
            assert "body" not in node, "Invalid type."
            return ir.FunctionType(self.VisitType(node["return"]), [self.VisitType(i) for i in node["params"] if i not in ["three dot"]], "three dot" in node["params"]).as_pointer()

        else:
            assert False, f"Unknown type '{node["type"]}'."

    @Timer
    def VisitCast(self, node):
        value, target = self.VisitValue(node["value"]), self.VisitType(node["target"])

        if value.type.is_pointer and isinstance(target, ir.IntType):
            return self.Builder.ptrtoint(value, target)

        elif isinstance(value.type, ir.FloatType):
            if isinstance(target, ir.IntType): return self.Builder.fptosi(value, target)
            if isinstance(target, ir.DoubleType): return self.Builder.fpext(value, target)
            if isinstance(target, ir.FloatType): return value

        elif isinstance(value.type, ir.DoubleType):
            if isinstance(target, ir.IntType): return self.Builder.fptosi(value, target)
            if isinstance(target, ir.FloatType): return self.Builder.fptrunc(value, target)
            if isinstance(target, ir.DoubleType): return value

        elif isinstance(value.type, ir.IntType):
            if target.is_pointer:
                return self.Builder.inttoptr(value, target)

            if isinstance(target, ir.FloatType) or isinstance(target, ir.DoubleType):
                return self.Builder.sitofp(value, target)
            
            if isinstance(target, ir.IntType):
                if target.width > value.type.width: return self.Builder.sext(value, target)
                else: return self.Builder.trunc(value, target)

        else:
            assert value.type.is_pointer and target.is_pointer, f"Cannot cast '{value.type}' to '{target}'."
            return self.Builder.bitcast(value, target)

    @Timer
    def VisitValue(self, node):
        if isinstance(node, ir.Value) or node is None:
            return node

        elif node["type"] in self.primitiveTypes or isinstance(node["type"], dict):
            return ir.Constant(self.VisitType(node["type"]), node["value"])

        elif node["type"] in ["identifier", "get", "get element", "get element pointer"]:
            value = self.VisitPointer(node)

            if isinstance(value, ir.GlobalVariable) and value.global_constant:
                return value.initializer

            if value.type.is_pointer and not value.type.is_opaque and not isinstance(value.type.pointee, ir.ArrayType):
                return self.Builder.load(value)

            else:
                return value

        elif node["type"] in ["not", "bitwise not"]:
            return self.Builder.not_(self.VisitValue(node["value"]))

        elif node["type"] in ["initializer list"]:
            return [self.VisitValue(i) for i in node["body"]]

        elif node["type"] in ["negate"]:
            value = self.VisitValue(node["value"])
            if isinstance(value, ir.Constant): return self.VisitConstExpr({"type": "negate", "value": value})
            return getattr(self.Builder, "fneg" if isinstance(value.type, ir.FloatType) else "neg")(value)

        elif node["type"] in ["dereference"]:
            return self.VisitValue(node["value"])

        elif node["type"] in ["expression"]:
            return self.VisitExpression(node)

        elif node["type"] in ["cast"]:
            return self.VisitCast(node)

        elif node["type"] in ["call"]:
            return self.VisitCall(node)

        elif node["type"] in ["null"]:
            return ir.Constant(ir.PointerType(), None)

        elif node["type"] in ["string"]:
            if node["value"] in self.stringCache:
                return self.stringCache[node["value"]]

            buffer = bytearray((node["value"] + "\0").encode("utf-8"))
            constant = ir.Constant(ir.ArrayType(ir.IntType(8), len(buffer)), buffer)
            _global = ir.GlobalVariable(self.module, constant.type, Mangler.MangleString(node["value"]))
            _global.linkage, _global.global_constant, _global.unnamed_addr, \
                _global.initializer, _global.align = "private", True, True, constant, 1
            self.stringCache[node["value"]] = _global
            return _global

        elif node["type"] in ["reference"]:
            return self.VisitPointer(node["value"])

        else:
            assert False, f"Unknown value '{node["type"]}'."

    @Timer
    def VisitPointer(self, node):
        assert self.scopeManager.Scope.local, "Cannot visit pointers in global scope."

        if isinstance(node, ir.PointerType) or isinstance(node, ir.Instruction) or isinstance(node, ir.Argument) or node is None:
            return node

        elif node["type"] in ["identifier"]:
            if self.scopeManager.Class is not None:
                if self.scopeManager.Class.Has(node["value"]):
                    value = self.Builder.load(self.scopeManager.Get("this"))
                    assert value.type.is_pointer, "Expected a pointer."
                    assert not value.type.is_opaque, "Expected a non-opaque pointer."
                    element = self.scopeManager.Class.Get(node["value"]).copy()
                    assert value.type.pointee == self.scopeManager.Class.type

                    if isinstance(element["type"], ir.Function):
                        element["pointer"], element["access"] = value, "public"
                        return element

                    return self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), self.scopeManager.Class.Index(node["value"]))])

            assert self.scopeManager.Has(node["value"]), f"Unknown identifier '{node["value"]}'."
            return self.scopeManager.Get(node["value"])

        elif node["type"] in ["get"]:
            return self.Builder.gep(self.VisitValue(node["value"]), [self.VisitValue(node["index"])])

        elif node["type"] in ["get element", "get element pointer"]:
            value = {"get element pointer": self.VisitValue, "get element": self.VisitPointer}[node["type"]](node["value"])
            assert value.type.is_pointer and not value.type.is_opaque and isinstance(value.type.pointee, ir.BaseStructType), f"Expected a class, got '{value.type}'."
            if self.scopeManager.Class and self.scopeManager.Class.Name == value.type.pointee.name: _class = self.scopeManager.Class
            else: _class = self.scopeManager.Get(value.type.pointee.name)
            assert _class.Has(node["element"]), f"Class '{value.type.pointee.name}' does not contain member '{node["element"]}'."
            element = _class.Get(node["element"]).copy()
            assert not (element["access"] != "public" and _class != self.scopeManager.Class), "Access violation."

            if isinstance(element["type"], ir.Function):
                if self.scopeManager.Class == _class:
                    element["access"] = "public"

                element["pointer"] = value
                return element

            return self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(node["element"]))])

        elif node["type"] in ["dereference"]:
            value = self.VisitValue(node["value"])
            assert value.type.is_pointer, "Expected a pointer."
            return value

        elif node["type"] in ["expression"]:
            value = self.VisitExpression(node)
            assert value.type.is_pointer, "Expected a pointer."
            return value

        elif node["type"] in ["cast"]:
            value = self.VisitCast(node)
            assert value.type.is_pointer, "Expected a pointer."
            return value

        elif node["type"] in ["call"]:
            value = self.VisitCall(node)
            assert value.type.is_pointer, "Expected a pointer."
            return value

        else:
            assert False, f"Unknown pointer '{node["type"]}'."

    @Timer
    def VisitConstructor(self, _class, ptr, params = []):
        for name, value in _class.Elements.items():
            if isinstance(value["type"], ir.BaseStructType):
                if self.VisitConstructor(self.scopeManager.Get(value["type"].name), self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]), (value["value"] if isinstance(value["value"], list) else [value["value"]]) if value["value"] else []):
                    continue

            if value["value"]:
                self.VisitAssign({"left": self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]), "right": value["value"]})

        if _class.Has(_class.RealName):
            return self.VisitCall({"value": {"type": "get element pointer", "value": ptr, "element": _class.RealName}, "params": params}, test = True)

        return False

    @Timer
    def VisitDestructor(self, _class, ptr):
        for name, value in _class.Elements.items():
            if isinstance(value["type"], ir.BaseStructType):
                self.VisitDestructor(self.scopeManager.Get(value["type"].name), self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]))

        if _class.Has(f"~{_class.RealName}"):
            self.VisitCall({"value": {"type": "get element pointer", "value": ptr, "element": f"~{_class.RealName}"}, "params": []})

    @Timer
    def VisitConstant(self, node):
        value, type = self.VisitConstExpr(node["value"]), self.VisitType(node["dataType"])
        _global = ir.GlobalVariable(self.module, type, node["name"])
        _global.global_constant, _global.initializer, _global.align = True, value, self.alignof(type).constant
        self.scopeManager.Set(node["name"], _global)

    @Timer
    def VisitDefine(self, node):
        assert self.scopeManager.Scope.local, "Define statements must be defined in local scope."

        if "body" in node:
            for i in node["body"]:
                self.Compile([i])

        else:
            assert not self.scopeManager.Scope.Has(node["name"]), f"Redefinition of '{node["name"]}'."
            dataType = self.VisitType(node["dataType"])

            if node["value"]:
                value = self.VisitValue(node["value"])

                if isinstance(value, ir.AllocaInstr) and hasattr(value, "_return"):
                    assert value.type.pointee == dataType, "Type mismatch."
                    self.scopeManager.Set(node["name"], value)
                    return

                if dataType.is_pointer and (isinstance(value, list) or value.type.is_pointer and isinstance(value.type.pointee, ir.ArrayType)):
                    if not isinstance(value, list): assert value.type.pointee.element == dataType.pointee, f"Type mismatch. (Expected '{dataType.pointee}', got '{value.type.pointee.element}'.)"
                    dataType = ir.ArrayType(dataType.pointee, len(value) if isinstance(value, list) else value.type.pointee.count).as_pointer()

            current = self.Builder.block
            self.Builder.position_at_start(self.Builder.function.entry_basic_block)
            ptr = self.Builder.alloca(dataType)
            self.Builder.position_at_end(current)
            self.scopeManager.Set(node["name"], ptr)

            if not dataType.is_pointer and isinstance(dataType, ir.BaseStructType):
                if not self.VisitConstructor(self.scopeManager.Get(dataType.name), ptr, (value if isinstance(value, list) else [value]) if node["value"] else []) and node["value"]:
                    assert value.type == dataType, f"Type mismatch for '{node['name']}'. (Expected '{dataType}', got '{value.type}'.)"
                    self.Builder.store(value, ptr, self.alignof(value).constant)

            else:
                if not node["value"]:
                    return

                if isinstance(value, list):
                    assert isinstance(dataType, ir.ArrayType), f"Type mismatch for '{node['name']}'. (Expected array type, got '{dataType}'.)"
                    assert len(value) == dataType.count, f"Array size mismatch for '{node['name']}'. (Expected {dataType.count}, got {len(value)})."

                    for index, i in enumerate(value):
                        assert i.type == dataType.element, f"Element type mismatch at '{node['name']}[{index}]'. (Expected '{dataType.element}', got '{i.type}'.)"
                        self.Builder.store(i, self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)]), self.alignof(i).constant)

                else:
                    assert value.type == dataType, f"Type mismatch for '{node['name']}'. (Expected '{dataType}', got '{value.type}'.)"
                    self.Builder.store(value, ptr, self.alignof(value).constant)

    @Timer
    def VisitAssign(self, node):
        assert self.scopeManager.Scope.local, "Assign statements must be defined in local scope."

        if "body" in node:
            for i in node["body"]:
                self.Compile([i])

        else:
            ptr = self.VisitPointer(node["left"])
            assert ptr.type.is_pointer, "Left side of an assignment must be a pointer."

            if isinstance(ptr.type.pointee, ir.BaseStructType):
                _class = self.scopeManager.Class if self.scopeManager.Class and self.scopeManager.Class.Name in [ptr.type.pointee.name] else self.scopeManager.Get(ptr.type.pointee.name)

                if node["right"]["type"] in ["expression"] and node["left"] in [node["right"]["left"], node["right"]["right"]] and _class.Has(f"op{node['right']['operator']}="):
                    value = self.TryPass(self.VisitValue(node["right"]["left" if node["left"] != node["right"]["left"] else "right"]))

                    if self.VisitCall({"value": {"type": "get element pointer", "value": ptr, "element": f"op{node['right']['operator']}="}, "params": [ptr, value]}, test = True):
                        return

            value = self.TryPass(self.VisitValue(node["right"]))

            if isinstance(ptr.type.pointee, ir.BaseStructType):
                if _class.Has("op=") and self.VisitCall({"value": {"type": "get element pointer", "value": ptr, "element": "op="}, "params": [ptr, value]}, test = True):
                    return

            self.Builder.store(value, ptr, self.alignof(value).constant)

    @Timer
    def VisitCall(self, node, test = False):
        assert self.scopeManager.Scope.local, "Call statements must be defined in local scope."
        funcs = self.VisitPointer(node["value"])
        func, name, highestScore = None, None, 0

        if not isinstance(funcs, list):
            funcs = [funcs]

        for index, _func in enumerate(funcs):
            _index, score = 0, 1

            if isinstance(_func, CompileTimeFunction):
                func = _func
                break

            if isinstance(_func, dict) and "access" in _func:
                assert _func["access"] == "public", "Access violation."
                if _func["pointer"] not in node["params"]: node["params"] = [_func["pointer"]] + node["params"]
                _func = _func["type"]

            else:
                if hasattr(_func, "_parentClass") and _func._parentClass != self.scopeManager.Class:
                    assert _func._parentClass.Get(Mangler.Demangle(_func.name)[0])["access"] == "public", "Access violation."

            if not isinstance(_func, ir.Function):
                _func = self.Builder.load(_func)

            name = _func.name

            for j in _func.function_type.args:
                if _index >= len(node["params"]):
                    score = -1
                    break

                self.PushBlockState()
                value = self.VisitValue(node["params"][_index])
                self.PopBlockState()

                type = value.type
                if hasattr(j, "_sret"): continue
                else: _index += 1

                if type.is_pointer and not type.is_opaque and isinstance(type.pointee, ir.ArrayType):
                    type = type.pointee.element.as_pointer()

                if type != (j._byval if hasattr(j, "_byval") else j):
                    score = -1
                    break

                score += 1

            if len(node["params"]) < _index if _func.function_type.var_arg else len(node["params"]) != _index:
                continue

            if score > highestScore:
                func, highestScore = _func, score

        assert func is not None or test, f"Invalid arguments for: '{name}'."
        if test and func is None: return False

        if isinstance(func, CompileTimeFunction):
            return func(*node["params"])

        _return, args, index = None, [], -1

        for i in node["params"]:
            index += 1

            if isinstance(func, ir.Function) and index < len(func.args):
                argument = func.args[index].type

                if hasattr(argument, "_sret"):
                    current = self.Builder.block
                    self.Builder.position_at_start(self.Builder.function.entry_basic_block)
                    _return = self.Builder.alloca(argument._sret)
                    self.Builder.position_at_end(current)
                    argument = func.args[index := index + 1].type
                    _return._return = True
                    args.append(_return)

                if hasattr(argument, "_byval"):
                    value = self.VisitPointer(i)
                    current = self.Builder.block
                    self.Builder.position_at_start(self.Builder.function.entry_basic_block)
                    ptr = self.Builder.alloca(value.type.pointee)
                    self.Builder.position_at_end(current)
                    self.Builder.call(self.memcpy, [ptr, value, self.sizeof(value.type.pointee), ir.Constant(ir.IntType(1), 0)])
                    value = ptr

                    if not isinstance(argument, ir.PointerType):
                        args.append(self.Builder.load(value, typ = argument))

                    else:
                        assert value.type.pointee == argument.pointee, \
                            f"Expected a pointer to '{argument.pointee.name}', got '{value.type.pointee.name}'."

                        args.append(value)

                else:
                    args.append(self.TryPass(self.VisitValue(i)))

            else:
                args.append(self.TryPass(self.VisitValue(i)))

        result = self.Builder.call(func, args)

        if _return is not None:
            return _return

        if hasattr(result.type, "_sret"):
            assert isinstance(result.type, ir.IntType), f"Expected an integer, got '{result.type}'."

            current = self.Builder.block
            self.Builder.position_at_start(self.Builder.function.entry_basic_block)
            ptr = self.Builder.alloca(result.type._sret)
            self.Builder.position_at_end(current)
            self.Builder.store(result, self.Builder.bitcast(ptr, result.type.as_pointer()), self.alignof(result.type._sret).constant)
            ptr._return, result = True, ptr

        return result

    @Timer
    def VisitFor(self, node):
        assert self.scopeManager.Scope.local, "For blocks must be defined in local scope."
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
        self.scopeManager.PushScope(Scope(local = True))
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

    @Timer
    def VisitWhile(self, node):
        assert self.scopeManager.Scope.local, "While blocks must be defined in local scope."
        checkBlock = self.Builder.append_basic_block()
        whileBlock = self.Builder.append_basic_block()
        endBlock = self.Builder.append_basic_block()

        self.Builder.branch(checkBlock)
        self.Builder.position_at_start(checkBlock)
        condition = self.VisitValue(node["condition"])
        self.Builder.cbranch(condition, whileBlock, endBlock)

        self.Builder.position_at_start(whileBlock)
        self.scopeManager.PushScope(Scope(local = True))
        self.Compile(node["body"])
        self.scopeManager.PopScope()

        if not self.Builder.block.is_terminated:
            self.Builder.branch(checkBlock)

        self.Builder.position_at_start(endBlock)

    @Timer
    def VisitReturn(self, node):
        assert self.scopeManager.Scope.local, "Return statements must be defined in local scope."

        if node["value"]:
            if hasattr(self.Builder.function.return_value.type, "_sret"):
                value = self.VisitPointer(node["value"])
                assert isinstance(value.type.pointee, ir.BaseStructType)
                self.InvokeDestructors(_except = value)

                if isinstance(self.Builder.function.return_value.type, ir.IntType):
                    self.Builder.ret(self.Builder.load(value, typ = self.Builder.function.return_value.type))

                else:
                    assert isinstance(self.Builder.function.return_value.type, ir.VoidType)
                    self.Builder.call(self.memcpy, [self.Builder.function.args[0], value, self.sizeof(value.type.pointee), ir.Constant(ir.IntType(1), 0)])
                    self.Builder.ret_void()

            else:
                value = self.VisitValue(node["value"])
                self.InvokeDestructors()
                self.Builder.ret(self.TryPass(value, _return = True))

        else:
            self.InvokeDestructors()
            self.Builder.ret_void()

    @Timer
    def VisitExpression(self, node):
        if "body" in node:
            for i in node["body"]:
                self.Compile([i])

        else:
            left, right = self.VisitValue(node["left"]), self.VisitValue(node["right"])

            if isinstance(left, ir.Constant) and isinstance(right, ir.Constant):
                return self.VisitConstExpr({"type": "expression", "operator": node["operator"], "left": left, "right": right})

            if left.type.is_pointer and right.type.is_pointer:
                if node["operator"] == "-":
                    return self.Builder.sub(self.Builder.ptrtoint(left, ir.IntType(64)), self.Builder.ptrtoint(right, ir.IntType(64)))

                elif node["operator"] in ["<", "<=", ">", ">=", "!=", "=="]:
                    return self.Builder.icmp_unsigned(node["operator"], left, right)

                else:
                    assert False, f"Invalid operator for pointers: '{node["operator"]}'."

            elif (left.type.is_pointer and isinstance(right.type, ir.IntType)) or (right.type.is_pointer and isinstance(left.type, ir.IntType)):
                ptr, index = (left, right) if left.type.is_pointer else (right, left)
                assert index.type.width in [32, 64], f"Invalid index size: '{index.type.width}'."

                if node["operator"] in ["+", "-"]:
                    return self.Builder.gep(ptr, [index if node["operator"] != "-" else self.Builder.neg(index)])

                else:
                    assert False, f"Invalid operator for pointers: '{node["operator"]}'."

            elif (isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType)) and (isinstance(right.type, ir.FloatType) or isinstance(right.type, ir.DoubleType)):
                assert left.type == right.type, f"Float size mismatch. ({left.type} != {right.type})"

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
                    assert False, f"Invalid operator for floats: '{node["operator"]}'."
            
            elif isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType):
                assert left.type.width == right.type.width, f"Integer size mismatch. ({left.type.width} != {right.type.width})"

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
                    assert False, f"Invalid operator for integers: '{node["operator"]}'."

            else:
                assert False, f"Invalid expression. ({left.type} {node["operator"]} {right.type})"