from llvmlite import ir

import os, sys, copy, time

from lexer import Lexer
from parser import Parser

def _to_string2(self):
    return f"{'u' if hasattr(self, '_unsigned') else 'i'}{self.width}"

def __eq__(self, other):
    if isinstance(other, ir.IntType):
        return self.width == other.width and hasattr(self, "_unsigned") == hasattr(other, "_unsigned")

    else:
        return False

ir.IntType._to_string2 = _to_string2
ir.IntType.__eq__ = __eq__

class Scope:
    def __init__(self, namespace = None, local = False):
        self.variables, self.children, self.parent = {}, [], None
        self.local, self.namespace = local, namespace
        self._compiler, self._instances = None, []

    def RegisterInstance(self, value):
        assert self.local, "Cannot register instance in non-local scope."
        self._instances.append(value)

    def InvokeDestructors(self, _except = None):
        for value in self._instances:
            if value is not _except:
                self._compiler.VisitDestructor(self._compiler.scopeManager.Get(value.type.pointee.name, types = [Class]), value)

        self._instances = []

    def Has(self, name, types = None):
        if name in self.variables and (any(isinstance(self.variables[name], type) for type in types) if types else True):
            return True

        for _name in self.variables:
            if not Mangler.IsMangled(_name):
                continue

            if Mangler.Demangle(_name)[0] in [name]:
                if types is None:
                    return True

                elif any(isinstance(self.variables[_name], type) for type in types):
                    return True

        return False

    def Set(self, name, value):
        self.variables[name] = value

    def Get(self, name, types = None):
        if name in self.variables and (any(isinstance(self.variables[name], type) for type in types) if types else True):
            return self.variables[name]

        matches = []

        for _name in self.variables:
            if not Mangler.IsMangled(_name):
                continue

            if Mangler.Demangle(_name)[0] in [name]:
                if types is None:
                    matches.append(self.variables[_name])

                elif any(isinstance(self.variables[_name], type) for type in types):
                    return self.variables[_name]

        assert matches, f"Unknown variable '{name}'."
        return matches if len(matches) > 1 else matches[0]

class ScopeManager:
    def __init__(self, compiler: "Compiler"):
        self.__scope = self.__global = Scope()
        self.__class, self.__template = [], []
        self.__compiler = compiler

    @property
    def Global(self):
        return self.__global

    @property
    def Scope(self):
        return self.__scope

    def PushScope(self, scope):
        self.__scope.children.append(scope)
        self.__scope, scope.parent = scope, self.__scope
        self.__scope._compiler = self.__compiler

    def PopScope(self):
        assert self.__scope.parent is not None, "No scope to pop."
        self.__scope.InvokeDestructors()
        scope = self.__scope

        if self.__scope.local:
            self.__scope.parent.children.remove(self.__scope)
            self.__scope.parent, self.__scope = None, self.__scope.parent

        else:
            self.__scope = self.__scope.parent

        return scope

    @property
    def Class(self):
        return self.__class[-1] if self.__class else None

    def PushClass(self, _class):
        self.__class.append(_class)

    def PopClass(self):
        assert self.__class, "No class to pop."
        return self.__class.pop()

    @property
    def Template(self):
        return self.__template[-1] if self.__template else None

    def PushTemplate(self, template):
        self.__template.append(template)

    def PopTemplate(self):
        assert self.__template, "No template to pop."
        return self.__template.pop()

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

    def Has(self, name, types = None):
        if Mangler.IsMangled(name):
            _, namespaces = Mangler.Demangle(name)

        else:
            names = name.split("::")
            name, namespaces = names[-1], names[:-1]

        if namespaces:
            return self.ScopeByNamespaces(namespaces).Has(name, types = types)

        else:
            scope = self.__scope

            while scope is not None:
                if scope.Has(name, types = types):
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

    def Get(self, name, types = None):
        if Mangler.IsMangled(name):
            _, namespaces = Mangler.Demangle(name)

        else:
            names = name.split("::")
            name, namespaces = names[-1], names[:-1]

        if namespaces:
            scope = self.ScopeByNamespaces(namespaces)
            assert scope.Has(name, types = types), f"Unknown variable: '{name}'"
            return scope.Get(name, types = types)

        else:
            scope = self.__scope

            while scope is not None:
                if scope.Has(name, types = types):
                    return scope.Get(name, types = types)

                scope = scope.parent

            assert False, f"Unknown variable: '{name}'"

class Class:
    def __init__(self, compiler, name, realName):
        self.__compiler, self.__name, self.__realName = compiler, name, realName
        self.type, self.parents, self.constructed = ir.global_context.get_identified_type(name), {}, []
        self.__elements, self.__functions = {}, {}

    @property
    def Name(self):
        return self.__name

    @property
    def RealName(self):
        return self.__realName

    @property
    def Elements(self):
        return {k: v.copy() for k, v in self.__elements.items() if v["access"] is not None}
    
    @property
    def Functions(self):
        return self.__functions.copy()

    def Cook(self):
        if self.type.elements is not None: return
        sizeof, alignof = self.__compiler.sizeof, self.__compiler.alignof
        elements, offset, alignment = {}, 0, 0

        __elements = self.__elements.copy()
        self.__elements = {name: {"type": parent.type, "value": None, "access": None} for name, parent in self.parents.items()}
        self.__elements.update(__elements)

        for element in self.__elements.values():
            alignment = max(alignment, alignof(element["type"]).constant)

        self.__elements.update({None: ...})

        for i in self.__elements:
            size = sizeof(self.__elements[i]["type"]).constant if i is not None else 0

            for j in [alignment, alignof(self.__elements[i]["type"]).constant if i is not None else 0]:
                if not j > 0:
                    continue

                if (offset % j) != 0 and (i is None or (offset % j) + size > j):
                    padding = j - (offset % j)
                    elements[f"<p@{offset}:{padding}>"] = {"type": ir.ArrayType(ir.IntType(8), padding), "value": None, "access": None}
                    offset += padding

            if i is not None:
                elements[i] = self.__elements[i]
                offset += size

        self.__elements = elements.copy()
        self.type.set_body(*[i["type"] for i in self.__elements.values()])
        self.type._class = self
        return self

    def RegisterParent(self, _class):
        assert _class.RealName not in self.parents, f"Duplicate parent: '{_class.RealName}'."
        self.parents[_class.RealName] = _class

    def RegisterElement(self, name, value):
        assert name not in self.__elements, f"Duplicate element: '{name}'."
        self.__elements[name] = value

    def RegisterFunction(self, name, value):
        assert name not in self.__functions, f"Duplicate function: '{name}'."
        self.__functions[name] = value

    def Index(self, name):
        return list(self.__elements.keys()).index(name)

    def Has(self, name, arguments = None):
        if arguments is not None:
            arguments = [self.__compiler.ProcessType(i) for i in arguments]

        if name in self.__elements and arguments is None:
            return self.__elements[name]["access"] == "public" or self.__compiler.scopeManager.Class == self

        if name in self.__functions and arguments is None:
            return self.__functions[name]["access"] == "public" or self.__compiler.scopeManager.Class == self

        for _name, function in self.__functions.items():
            if not Mangler.IsMangled(_name):
                continue

            if function["access"] != "public" and self.__compiler.scopeManager.Class != self:
                continue

            if Mangler.Demangle(_name)[0] in [name]:
                args = function["type"].function_type.args
                args = args[2:] if hasattr(args[0], "_sret") else args[1:]

                if arguments is None:
                    return True

                if len(arguments) != len(args):
                    continue

                match = True

                for index, type in enumerate(args):
                    if len(arguments) > index:
                        if hasattr(type, "_reference"):
                            type = type.pointee

                        if hasattr(type, "_byval"):
                            type = type._byval

                        if type != arguments[index]:
                            match = False
                            break

                if match:
                    return True

        return False

    def Get(self, name, arguments = None, pointer = None):
        if arguments is not None:
            arguments = [self.__compiler.ProcessType(i) for i in arguments]

        if name in self.__elements and arguments is None:
            assert self.__elements[name]["access"] == "public" or self.__compiler.scopeManager.Class == self, f"Function '{name}' is not accessible."

            if pointer is not None:
                return self.__compiler.Builder.gep(pointer, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), self.Index(name))])

            else:
                return self.__elements[name].copy()

        if name in self.__functions and arguments is None:
            function = self.__functions[name].copy()
            assert function["access"] == "public" or self.__compiler.scopeManager.Class == self, \
                f"Function '{name}' is not accessible."

            if pointer is not None:
                function["pointer"] = pointer

            return function

        matches, state = [], 0

        for _name, function in self.__functions.items():
            if not Mangler.IsMangled(_name):
                continue

            if Mangler.Demangle(_name)[0] in [name]:
                if function["access"] != "public" and self.__compiler.scopeManager.Class != self:
                    if state < 1: state = 1
                    continue

                function = function.copy()

                if pointer is not None:
                    function["pointer"] = pointer

                args = function["type"].function_type.args
                args = args[2:] if hasattr(args[0], "_sret") else args[1:]

                if arguments is None:
                    matches.append(function)
                    continue

                if len(arguments) != len(args):
                    continue

                match = True

                for index, type in enumerate(args):
                    if len(arguments) > index:
                        if hasattr(type, "_reference"):
                            type = type.pointee

                        if hasattr(type, "_byval"):
                            type = type._byval

                        if type != arguments[index]:
                            match = False
                            break

                if match:
                    return function

                else:
                    state = 2

        assert not (len(matches) == 0 and state == 0), f"Class '{self.Name}' doesn't contain any member named '{name}'."
        assert not (len(matches) == 0 and state == 1), f"Function '{name}' is not accessible."
        assert not (len(matches) == 0 and state == 2 and arguments is not None), \
            f"Invalid arguments for: '{name}'. ({', '.join([str(type) for type in arguments]) if arguments else 'nothing'})"
        return matches if len(matches) > 1 else matches[0]

class Template:
    def __init__(self, compiler, scope, body, params):
        self.__compiler, self.__scope = compiler, scope
        self.__instances, self.__current = {}, None
        self.__body, self.__params = body, params

    def Set(self, type):
        assert self.__current, "No current template instance."
        self.__instances[self.__current] = type
        self.__current = None

    def Get(self, params):
        assert not self.__current, "Template instantiation in progress."
        assert len(self.__params) == len(params), "Parameter count mismatch."
        params = tuple(self.__compiler.VisitType(param) for param in params)

        if params in self.__instances:
            return self.__instances[params]

        scope, self.__compiler.scopeManager._ScopeManager__scope = \
            self.__compiler.scopeManager._ScopeManager__scope, self.__scope

        for index, i in enumerate(self.__params):
            self.__scope.Set(i["name"], params[index])

        self.__current = params
        body = copy.deepcopy(self.__body)
        body["name"], body["_name"] = Mangler.MangleClass(body["name"], params), body["name"]
        mangling, self.__compiler.mangling = self.__compiler.mangling, True
        self.__compiler.scopeManager.PushTemplate(self)
        self.__compiler.Compile([body])
        self.__compiler.scopeManager.PopTemplate()
        self.__compiler.mangling = mangling

        for index, i in enumerate(self.__params):
            del self.__scope.variables[i["name"]]

        self.__compiler.scopeManager._ScopeManager__scope = scope
        return self.__instances[params]

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

class AddressOf(CompileTimeFunction):
    def __init__(self, compiler):
        super().__init__(compiler)

    def __call__(self, _value):
        try:
            value = self.compiler.VisitPointer(_value)

        except:
            value = self.compiler.VisitValue(_value)

        if isinstance(value, ir.LoadInstr):
            self.compiler.Builder.remove(value)
            value = value.operands[0]

        if isinstance(value, ir.Constant) and hasattr(value, "_ptr"):
            value = value._ptr

        assert value.type.is_pointer and value.type.pointee == _value.type, \
            f"Failed to get address of '{value}'."

        return value

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
                _digit, ignore = "", 0

                while len(mangle) > index:
                    names[-1] += mangle[index]

                    if mangle[index] in ["I", "F"]:
                        ignore += 1

                    elif mangle[index] in ["E"]:
                        ignore -= 1

                        if not ignore:
                            break

                    while mangle[index].isdigit():
                        _digit += mangle[index]
                        index += 1

                    if _digit:
                        names[-1] += mangle[index:index + int(_digit)]
                        index += int(_digit)

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
    return func

    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        color = "\033[92m" if duration < 0.0001 else "\033[93m" if duration < 1 else "\033[91m"
        if color not in ["\033[92m"]: print(f"[TIMER] '{func.__name__}' took {color}{duration:.6f}\033[0m seconds.")
        return result

    return wrapper

class Compiler:
    def __init__(self):
        self.module = ir.Module("main")
        self.scopeManager = ScopeManager(self)
        self.primitiveTypes = {
            "void": ir.VoidType(), "bool": ir.IntType(1), "char": ir.IntType(32),
            "i8": ir.IntType(8), "i16": ir.IntType(16), "i32": ir.IntType(32), "i64": ir.IntType(64), "i128": ir.IntType(128),
            "f32": ir.FloatType(), "f64": ir.DoubleType()
        }

        _instance_cache, ir.IntType._instance_cache = ir.IntType._instance_cache, {}
        self.primitiveTypes.update({"u8": ir.IntType(8), "u16": ir.IntType(16), "u32": ir.IntType(32), "u64": ir.IntType(64), "u128": ir.IntType(128)})
        ir.IntType._instance_cache = {} # _instance_cache

        for name, type in self.primitiveTypes.items():
            if name.startswith("u"): type._unsigned = True
            self.scopeManager.Set(name, type)

        self.scopeManager.Set("decltype", DeclType(self))
        self.scopeManager.Set("sizeof", sizeof := SizeOf(self))
        self.scopeManager.Set("alignof", alignof := AlignOf(self))
        self.scopeManager.Set("offsetof", offsetof := OffsetOf(self))
        self.scopeManager.Set("addressof", addressof := AddressOf(self))
        self.sizeof, self.alignof, self.offsetof, self.addressof = sizeof, alignof, offsetof, addressof
        self.memcpy = ir.Function(self.module, ir.FunctionType(ir.VoidType(), [ir.PointerType(), ir.PointerType(), ir.IntType(64), ir.IntType(1)]), "llvm.memcpy.p0.p0.i64")
        self.malloc = ir.Function(self.module, ir.FunctionType(ir.IntType(8).as_pointer(), [ir.IntType(64)]), "malloc")
        self.free = ir.Function(self.module, ir.FunctionType(ir.VoidType(), [ir.IntType(8).as_pointer()]), "free")
        self.includePaths, self.entryPoints = [], ["main", "WinMain", "DllMain"]
        self.stringCache, self.builderStack, self.mangling = {}, [], True
        self.scopeManager.Set("malloc", self.malloc)
        self.scopeManager.Set("free", self.free)
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

    @property
    def LoopBlock(self):
        assert hasattr(self.Builder, "_blocks") and 0 < len(self.Builder._blocks), "No loop block."
        return self.Builder._blocks[-1][0]

    @property
    def EndBlock(self):
        assert hasattr(self.Builder, "_blocks") and 0 < len(self.Builder._blocks), "No end block."
        return self.Builder._blocks[-1][1]

    def PushBlocks(self, loopBlock, endBlock):
        if not hasattr(self.Builder, "_blocks"): self.Builder._blocks = []
        self.Builder._blocks.append((loopBlock, endBlock))

    def PopBlocks(self):
        assert hasattr(self.Builder, "_blocks") and 0 < len(self.Builder._blocks), "No block to pop."
        return self.Builder._blocks.pop()

    def InvokeDestructors(self, _except = None):
        scope = self.scopeManager.Scope

        while scope.local:
            scope.InvokeDestructors(_except = _except)
            scope = scope.parent

    def Compile(self, ast):
        for node in ast:
            if node is None: continue
            if self.Builder is not None and self.Builder.block.is_terminated: break
            name = f"Visit{"".join([i.capitalize() for i in node["type"].split(" ")])}"
            assert hasattr(self, name), f"Unknown node '{node["type"]}'."
            getattr(self, name)(node)

        return self.module

    def ProcessType(self, type):
        try:
            type = self.VisitType(type)

        except:
            type = self.VisitValue(type).type

        if type.is_pointer and not type.is_opaque and isinstance(type.pointee, ir.ArrayType):
            return type.pointee.element.as_pointer()

        return type

    def TryPack(self, return_, arguments):
        _return, names, types, mutables = ir.VoidType(), [], [], []

        for index, (name, type, mutable) in enumerate([(None, return_, None)] + arguments):
            if isinstance(type, ir.BaseStructType):
                if (size := self.sizeof(type).constant) > 8:
                    new = type.as_pointer()
                    if index != 0: new._byval, type = type, new
                    else: new._sret, type = type, new
                    names.append(name)
                    types.append(type)
                    mutables.append(mutable)
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
                mutables.append(mutable)

            else:
                _return = type

        return _return, tuple(names), tuple(types), tuple(mutables)

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
    def VisitConstExpr(self, node, target = None):
        if isinstance(node, ir.Constant):
            return node

        elif node["type"] in ["list initialization"]:
            elements, result = [self.VisitConstExpr(i) for i in node["body"]], []

            for element in self.scopeManager.Get(node["name"], types = [Class])._Class__elements.values():
                if element["access"] is None:
                    result.append(ir.Constant(element["type"].count, [ir.Constant(ir.IntType(8), 0)] * element["type"].count))

                else:
                    assert elements or element["value"], "Not enough elements in list initialization."
                    result.append(elements.pop(0) if elements else self.VisitConstExpr(element["value"]))

            assert not elements, "Too many elements in list initialization."
            return ir.Constant(self.scopeManager.Get(node["name"]).type, result)

        elif node["type"] in ["initializer list"]:
            return self.VisitConstExpr({"type": "list initialization", "name": target.name, "body": node["body"]})

        elif node["type"] in ["string"]:
            buffer = bytearray((node["value"] + "\0").encode("utf-8"))
            return ir.Constant(ir.ArrayType(ir.IntType(8), len(buffer)), buffer)

        elif node["type"] in ["expression"]:
            left, right = self.VisitConstExpr(node["left"]), self.VisitConstExpr(node["right"])

            if (isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType)) and (isinstance(right.type, ir.FloatType) or isinstance(right.type, ir.DoubleType)):
                assert left.type == right.type, f"Float size mismatch. ({left.type} {node["operator"]} {right.type})"

            elif isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType):
                assert left.type.width == right.type.width, f"Integer size mismatch. ({left.type._to_string2()} {node["operator"]} {right.type._to_string2()})"
                assert hasattr(left.type, "_unsigned") == hasattr(right.type, "_unsigned"), f"Integer sign mismatch. ({left.type._to_string2()} {node["operator"]} {right.type._to_string2()})"

            else:
                assert False, f"Invalid expression. ({left.type} {node["operator"]} {right.type})"

            assert node["operator"] not in ["&", "|", "^", ">>", "<<"] or isinstance(left.type, ir.IntType), "Bitwise operations can only be performed on integers."
            assert node["operator"] not in ["&&", "||"] or (isinstance(left.type, ir.IntType) and left.type.width == 1), "Logical operations can only be performed on booleans."
            return ir.Constant(ir.IntType(1) if node["operator"] in ["<", "<=", ">", ">=", "!=", "=="] else (ir.FloatType() if node["operator"] in ["/", "%"] and not (isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType)) else left.type), eval(f"left.constant {node["operator"]} right.constant"))

        elif node["type"] in self.primitiveTypes:
            return ir.Constant(self.VisitType(node["type"]), node["value"])

        elif node["type"] in ["identifier"]:
            value = self.VisitPointer(node)

            if isinstance(value, ir.GlobalVariable) and value.global_constant:
                value = value.initializer

            assert not value.type.is_pointer, "Expected a constant."
            return value

        elif node["type"] in ["cast"]:
            value, target = self.VisitConstExpr(node["value"]), self.VisitType(node["target"])

            if isinstance(target, ir.IntType):
                return ir.Constant(target, int(value.constant) if target.width != 1 else bool(value.constant))

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
                assert isinstance(value.type, ir.IntType), f"Expected an {type._to_string2()}, got {value.type}."
                assert value.type == type, f"Expected an {type._to_string2()}, got {value.type._to_string2()}."

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

        for parent in node["parents"]:
            self.scopeManager.Class.RegisterParent(self.VisitType(parent)._class)

        for _name, member in node["members"].items():
            self.scopeManager.Class.RegisterElement(_name, {"type": self.VisitType(member["dataType"]), "value": member["value"], "access": "private" if member["private"] else "public"})

        self.scopeManager.Scope.parent.Set(node["name"], _class := self.scopeManager.Class.Cook())

        if self.scopeManager.Template:
            self.scopeManager.Template.Set(_class.type)

        for i in node["impl"]:
            i = copy.deepcopy(i)

            if i["type"] in ["constructor", "destructor"]:
                i["private"] = False
                i["name"] = f"~{name}" if i["type"] != "constructor" else name
                i["return"] = "void"
                i["type"] = "func"

            if i["type"] in ["operator"]:
                i["type"] = "func"
                i["name"] = f"op{i['operator']}"
                del i["operator"]

            assert i["type"] == "func", f"Invalid implementation type: '{i["type"]}'."
            i["params"] = [{"type": self.scopeManager.Class.type.as_pointer(), "name": "this", "mutable": True}] + i["params"]
            func = {"type": self.VisitFunc(i, body = False), "access": "private" if i["private"] else "public"}
            self.scopeManager.Class.RegisterFunction(func["type"].name, func)
            impl.append(i)

        for i in impl:
            self.VisitFunc(i, override = True)

        self.scopeManager.PopScope()
        self.scopeManager.PopClass()

    @Timer
    def VisitInclude(self, node):
        assert not self.scopeManager.Scope.local, "Includes must be made in global scope."

        for i in node["modules"].copy():
            source = None

            for j in ["./"] + self.includePaths:
                path = os.path.join(j, i)

                if os.path.exists(path):
                    if os.path.isfile(path):
                        if path in self.__includedFiles: break
                        else: self.__includedFiles.append(path)
                        source = open(path, "r").read()
                        break

                    else:
                        path = os.path.join(path, "Entry.div")
                        assert os.path.exists(path), "Module entry point not found."
                        if path in self.__includedFiles: break
                        else: self.__includedFiles.append(path)
                        source = open(path, "r").read()
                        break

            if source is None and path in self.__includedFiles:
                continue

            lexer, parser = Lexer(), Parser()
            assert source is not None, f"Module '{i}' not found."
            parser.parse(lexer.tokenize(source))
            self.Compile(parser.ast["body"])

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
                _class = self.scopeManager.Get(namespaces[-1], types = [Class])

                if isinstance(_class, Class):
                    assert _class.Has(name), f"Class '{namespaces[-1]}' does not have function '{name}'."
                    node["params"] = [{"type": _class.type.as_pointer(), "name": "this", "mutable": True}] + node["params"]
                    self.scopeManager.PushClass(_class)
                    classState = True

        for index, param in enumerate(node["params"]):
            if param["type"] != "three dot":
                arguments += [(param["name"], self.VisitType(param["type"]), param["mutable"])]

            else:
                assert index == len(node["params"]) - 1, "Three dots must be the last parameter."
                threeDots = True

        _return, names, types, mutables = self.TryPack(self.VisitType(node["return"]), arguments)

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

        if "body" in node and body:
            self.PushBuilder(ir.IRBuilder(func.append_basic_block()))
            self.scopeManager.PushScope(Scope(local = True))

            for index, (name, type, mutable) in enumerate(zip(names, types, mutables)):
                if hasattr(func.args[index].type, "_byval"):
                    current = self.Builder.block
                    self.Builder.position_at_start(self.Builder.function.entry_basic_block)
                    ptr = self.Builder.alloca(func.args[index].type._byval)
                    self.Builder.position_at_end(current)
                    ptr.type._mutable = mutable
                    ptr.type._name = name

                    if isinstance(func.args[index].type._byval, ir.BaseStructType):
                        self.scopeManager.Scope.RegisterInstance(ptr)

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
                    ptr.type._mutable = mutable
                    ptr.type._name = name

            if "constructors" in node:
                for constructor in node["constructors"]:
                    _class = self.scopeManager.Get(constructor["class"], types = [Class])
                    ptr = func.args[1] if hasattr(func.args[0].type, "_sret") else func.args[0]
                    ptr = self.VisitCast({"type": "cast", "value": ptr, "target": _class.type.as_pointer()})
                    self.VisitConstructor(_class, ptr, [self.VisitValue(i) for i in constructor["params"]])
                    self.scopeManager.Class.constructed.append(_class.RealName)

            self.Compile(node["body"])
            self.scopeManager.PopScope()

            if not self.Builder.block.is_terminated:
                assert func.return_value.type == ir.VoidType(), f"Function '{node["name"]}' must return a value."
                self.Builder.ret_void()

            self.PopBuilder()

        if classState:
            self.scopeManager.PopClass()

        return func

    @Timer
    def VisitIf(self, node):
        assert self.scopeManager.Scope.local, "If blocks must be defined in local scope."
        endBlock = None

        while node is not None:
            hasElse = "else" in node and (node["else"]["body"] is not None or "condition" in node["else"])

            if "condition" in node:
                ifBlock = self.Builder.append_basic_block() if node["body"] else ((endBlock := self.Builder.append_basic_block()) if endBlock is None else endBlock)
                elseBlock = self.Builder.append_basic_block() if hasElse else ((endBlock := self.Builder.append_basic_block()) if endBlock is None else endBlock)
                self.Builder.cbranch(self.VisitValue(node["condition"]), ifBlock, elseBlock)

                if node["body"]:
                    self.Builder.position_at_end(ifBlock)
                    self.scopeManager.PushScope(Scope(local = True))
                    self.Compile(node["body"])
                    self.scopeManager.PopScope()

                    if not self.Builder.block.is_terminated:
                        self.Builder.branch((endBlock := self.Builder.append_basic_block()) if endBlock is None else endBlock)

                self.Builder.position_at_end(elseBlock)

            else:
                self.scopeManager.PushScope(Scope(local = True))
                self.Compile(node["body"])
                self.scopeManager.PopScope()

                if not self.Builder.block.is_terminated:
                    self.Builder.branch((endBlock := self.Builder.append_basic_block()) if endBlock is None else endBlock)

            node = node["else"] if hasElse else None

        if endBlock is not None:
            self.Builder.position_at_end(endBlock)

    @Timer
    def VisitTypedef(self, node):
        assert not self.scopeManager.Scope.local, "Types must be defined in global scope."
        self.scopeManager.Set(node["name"], self.VisitType(node["value"]))

    @Timer
    def VisitType(self, node):
        if isinstance(node, str):
            node = {"type": "identifier", "value": node}

        if not isinstance(node, dict):
            if hasattr(node, "type"):
                return node.type

            return node

        elif node["type"] in ["identifier"]:
            assert self.scopeManager.Has(node["value"]), f"Unknown type '{node["value"]}'."
            type = self.scopeManager.Get(node["value"], types = [ir.Type, Class])
            if isinstance(type, Class): type = type.type
            return type

        elif node["type"] in ["call"]:
            type = self.VisitCall(node)
            if isinstance(type, Class): type = type.type
            assert isinstance(type, ir.Type), "Expected a type."
            return type

        elif node["type"] in ["pointer"]:
            type = self.VisitType(node["value"])
            assert not hasattr(type, "_reference"), f"Cannot have a pointer to a reference."
            return ir.IntType(8).as_pointer() if isinstance(type, ir.VoidType) else type.as_pointer()

        elif node["type"] in ["reference"]:
            type = self.VisitType({"type": "pointer", "value": node["value"]})
            type._reference = True
            return type

        elif node["type"] in ["array"]:
            if node["size"]:
                return ir.ArrayType(self.VisitType(node["value"]), node["size"])
            
            else:
                return self.VisitType(node["value"]).as_pointer()

        elif node["type"] in ["template"]:
            assert self.scopeManager.Has(node["value"]), f"Unknown type '{node["value"]}'."
            return self.scopeManager.Get(node["value"], types = [Template]).Get(node["params"])

        elif node["type"] in ["function"]:
            assert "body" not in node, "Invalid type."
            return ir.FunctionType(self.VisitType(node["return"]), [self.VisitType(i) for i in node["params"] if i not in ["three dot"]], "three dot" in node["params"]).as_pointer()

        else:
            assert False, f"Unknown type '{node["type"]}'."

    @Timer
    def VisitCast(self, node):
        value, target = self.VisitValue(node["value"]), self.VisitType(node["target"])
        assert value.type != target, f"Redundant cast. ({value.type} to {target})"

        if isinstance(value, ir.Constant):
            return self.VisitConstExpr({"type": "cast", "value": value, "target": target})

        elif value.type.is_pointer and isinstance(target, ir.IntType):
            return self.Builder.ptrtoint(value, target)

        elif value.type.is_pointer and isinstance(value.type.pointee, ir.BaseStructType) and target.is_pointer and isinstance(target.pointee, ir.BaseStructType):
            valueClass = self.scopeManager.Get(value.type.pointee.name, types = [Class])
            targetClass = self.scopeManager.Get(target.pointee.name, types = [Class])

            assert (left := targetClass.RealName in valueClass._Class__elements) or valueClass.RealName in targetClass._Class__elements, \
                f"Class '{value.type.pointee.name}' is not related to '{target.pointee.name}'."

            index = valueClass.Index(targetClass.RealName) if left else targetClass.Index(valueClass.RealName)
            if index != 0: value = self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index if left else -index)])
            return self.Builder.bitcast(value, target)

        elif isinstance(value.type, ir.FloatType):
            if isinstance(target, ir.IntType):
                if hasattr(target, "_unsigned"): return self.Builder.fptoui(value, target)
                else: return self.Builder.fptosi(value, target)

            if isinstance(target, ir.DoubleType):
                return self.Builder.fpext(value, target)

        elif isinstance(value.type, ir.DoubleType):
            if isinstance(target, ir.IntType):
                if hasattr(target, "_unsigned"): return self.Builder.fptoui(value, target)
                else: return self.Builder.fptosi(value, target)

            if isinstance(target, ir.FloatType):
                return self.Builder.fptrunc(value, target)

        elif isinstance(value.type, ir.IntType):
            if target.is_pointer:
                return self.Builder.inttoptr(value, target)

            if isinstance(target, ir.FloatType) or isinstance(target, ir.DoubleType):
                if hasattr(value.type, "_unsigned"): return self.Builder.uitofp(value, target)
                else: return self.Builder.sitofp(value, target)

            if isinstance(target, ir.IntType):
                if target.width > value.type.width: return self.Builder.sext(value, target)
                else: return self.Builder.trunc(value, target)

        else:
            assert value.type.is_pointer and target.is_pointer, f"Cannot cast '{value.type}' to '{target}'."
            return self.Builder.bitcast(value, target)

    @Timer
    def VisitValue(self, node):
        if not isinstance(node, dict) or "access" in node:
            return node

        elif node["type"] in self.primitiveTypes or isinstance(node["type"], dict):
            return ir.Constant(self.VisitType(node["type"]), node["value"])

        elif node["type"] in ["identifier", "assign", "get", "get element", "get element pointer"]:
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

        elif node["type"] in ["list initialization"]:
            return self.Builder.load(self.VisitPointer(node))

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

        elif node["type"] in ["new"]:
            return self.VisitNew(node)

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
            constant._ptr = _global
            return _global

        elif node["type"] in ["address of"]:
            return self.VisitPointer(node["value"])

        else:
            assert False, f"Unknown value '{node["type"]}'."

    @Timer
    def VisitPointer(self, node):
        if not isinstance(node, dict) or "access" in node:
            return node

        elif node["type"] in ["identifier"]:
            if self.scopeManager.Scope.Has(node["value"]):
                return self.scopeManager.Scope.Get(node["value"])

            if self.scopeManager.Class is not None:
                if self.scopeManager.Class.Has(node["value"]):
                    value = self.Builder.load(self.scopeManager.Get("this"))
                    assert value.type.is_pointer, "Expected a pointer."
                    assert not value.type.is_opaque, "Expected a non-opaque pointer."
                    return self.scopeManager.Class.Get(node["value"], pointer = value)

            assert self.scopeManager.Has(node["value"]), f"Unknown identifier '{node["value"]}'."
            return self.scopeManager.Get(node["value"])

        elif node["type"] in ["get"]:
            value, index = self.VisitValue(node["value"]), self.VisitValue(node["index"])

            if isinstance(value.type, ir.BaseStructType):
                _class = self.scopeManager.Get(value.type.name, types = [Class])
                function = _class.Get("op[]", arguments = [index], pointer = self.addressof(value))
                return self.VisitCall({"value": function, "params": [index]})

            return self.Builder.gep(value, [index])

        elif node["type"] in ["get element", "get element pointer"]:
            value = {"get element pointer": self.VisitValue, "get element": self.VisitPointer}[node["type"]](node["value"])
            if hasattr(value.type.pointee, "_reference"): value = self.Builder.load(value)
            assert value.type.is_pointer and not value.type.is_opaque and isinstance(value.type.pointee, ir.BaseStructType), f"Expected a class, got '{value.type}'."
            _class = self.scopeManager.Get(value.type.pointee.name, types = [Class])
            return _class.Get(node["element"], pointer = value)

        elif node["type"] in ["list initialization"]:
            _class = self.scopeManager.Get(node["name"], types = [Class])
            assert isinstance(_class, Class), f"Unknown class '{node["name"]}'."
            current = self.Builder.block
            self.Builder.position_at_start(self.Builder.function.entry_basic_block)
            ptr = self.Builder.alloca(_class.type)
            self.Builder.position_at_end(current)
            self.VisitConstructor(_class, ptr, [self.VisitValue(i) for i in node["body"]])
            self.scopeManager.Scope.RegisterInstance(ptr)
            return ptr

        elif node["type"] in ["dereference"]:
            value = self.VisitValue(node["value"])
            assert value.type.is_pointer, "Expected a pointer."
            return value

        elif node["type"] in ["expression"]:
            value = self.VisitExpression(node)

            if isinstance(value, ir.LoadInstr) and hasattr(value.operands[0], "_return"):
                self.Builder.remove(value)
                value = value.operands[0]

            assert value.type.is_pointer, "Expected a pointer."
            return value

        elif node["type"] in ["cast"]:
            value = self.VisitCast(node)
            assert value.type.is_pointer, "Expected a pointer."
            return value

        elif node["type"] in ["call"]:
            value = self.VisitCall(node)

            if isinstance(value, ir.LoadInstr) and hasattr(value.operands[0], "_return"):
                self.Builder.remove(value)
                value = value.operands[0]

            assert value.type.is_pointer, "Expected a pointer."
            return value
        
        elif node["type"] in ["new"]:
            return self.VisitNew(node)

        elif node["type"] in ["assign"]:
            return self.VisitAssign(node)

        else:
            assert False, f"Unknown pointer '{node["type"]}'."

    @Timer
    def VisitContinue(self, node):
        self.Builder.branch(self.LoopBlock)

    @Timer
    def VisitBreak(self, node):
        self.Builder.branch(self.EndBlock)

    @Timer
    def VisitConstructor(self, _class, ptr, params = []):
        needCopy = len(params) == 1 and params[0].type == _class.type
        isConstructed = _class.RealName in _class.constructed
        hasConstructor = _class.Has(_class.RealName)

        if needCopy and not (hasConstructor and not isConstructed):
            params[0] = self.addressof(params[0])

        for index, (name, value) in enumerate(_class.Elements.items()):
            _value = (params[index] if not (hasConstructor and not isConstructed) and index < len(params) else self.VisitValue(value["value"]))

            if needCopy and not (hasConstructor and not isConstructed):
                _value = self.Builder.load(self.Builder.gep(params[0], [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]))

            if isinstance(value["type"], ir.BaseStructType):
                self.VisitConstructor(self.scopeManager.Get(value["type"].name, types = [Class]), self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]), (_value if isinstance(_value, list) else [_value]) if _value else [])
                continue

            if _value is not None:
                self.VisitAssign({"left": self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]), "right": _value}, ignore = True)

        if hasConstructor and not isConstructed:
            assert _class.Has(_class.RealName, arguments = params), \
                f"Class '{_class.RealName}' does not have a constructor that takes {('(' + ', '.join([str(i.type) for i in params]) + ')') if params else 'nothing'}."

            return self.VisitCall({"value": _class.Get(_class.RealName, arguments = params, pointer = ptr), "params": params})

        else:
            assert len(params) <= len(_class.Elements), "Too many parameters."

    @Timer
    def VisitDestructor(self, _class, ptr):
        for name, value in _class.Elements.items():
            if isinstance(value["type"], ir.BaseStructType):
                self.VisitDestructor(self.scopeManager.Get(value["type"].name, types = [Class]), self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]))

        if _class.Has(f"~{_class.RealName}"):
            return self.VisitCall({"value": _class.Get(f"~{_class.RealName}", arguments = [], pointer = ptr), "params": []})

    @Timer
    def VisitConstant(self, node):
        type = self.VisitType(node["dataType"])
        value = self.VisitConstExpr(node["value"], target = type)
        _global = ir.GlobalVariable(self.module, type, node["name"])
        _global.global_constant, _global.initializer, _global.align = True, value, self.alignof(type).constant
        self.scopeManager.Set(node["name"], _global)
        value._ptr = _global

    @Timer
    def VisitDefine(self, node):
        assert self.scopeManager.Scope.local, "Define statements must be defined in local scope."

        if "body" in node:
            for i in node["body"]:
                self.Compile([i])

        else:
            assert not self.scopeManager.Scope.Has(node["name"]), f"Redefinition of '{node["name"]}'."
            assert not (node["name"] in ["this"] and self.scopeManager.Class is not None), "Illegal variable name."
            dataType = self.VisitType(node["dataType"])

            if node["value"] is not None:
                value = self.VisitValue(node["value"])

                if isinstance(value, ir.LoadInstr) and hasattr(value.operands[0], "_return"):
                    assert value.type == dataType, "Type mismatch."
                    self.scopeManager.Set(node["name"], value.operands[0])
                    value.operands[0].type._mutable = node["mutable"]
                    value.operands[0].type._name = node["name"]
                    self.Builder.remove(value)
                    return

                if dataType.is_pointer and (isinstance(value, list) or value.type.is_pointer and not value.type.is_opaque and isinstance(value.type.pointee, ir.ArrayType)):
                    if not isinstance(value, list): assert value.type.pointee.element == dataType.pointee, f"Type mismatch. (Expected '{dataType.pointee}', got '{value.type.pointee.element}'.)"
                    dataType = ir.ArrayType(dataType.pointee, len(value) if isinstance(value, list) else value.type.pointee.count)

            current = self.Builder.block
            self.Builder.position_at_start(self.Builder.function.entry_basic_block)
            ptr = self.Builder.alloca(dataType)
            self.Builder.position_at_end(current)
            self.scopeManager.Set(node["name"], ptr)
            ptr.type._mutable = node["mutable"]
            ptr.type._name = node["name"]

            if isinstance(dataType, ir.BaseStructType):
                self.VisitConstructor(self.scopeManager.Get(dataType.name, types = [Class]), ptr, (value if isinstance(value, list) else [value]) if node["value"] else [])
                self.scopeManager.Scope.RegisterInstance(ptr)
                return

            if node["value"] is not None:
                if isinstance(value, list):
                    assert isinstance(dataType, ir.ArrayType), f"Type mismatch for '{node['name']}'. (Expected array type, got '{dataType}'.)"
                    assert len(value) == dataType.count, f"Array size mismatch for '{node['name']}'. (Expected {dataType.count}, got {len(value)})."

                    for index, i in enumerate(value):
                        assert i.type == dataType.element, f"Element type mismatch at '{node['name']}[{index}]'. (Expected '{dataType.element}', got '{i.type}'.)"
                        self.Builder.store(i, self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)]), self.alignof(i).constant)

                else:
                    if hasattr(dataType, "_reference") and dataType != value.type:
                        value = self.addressof(value)

                    if hasattr(value.type, "_mutable") and hasattr(value.type, "_name"):
                        assert ptr.type._mutable == value.type._mutable, f"Mutability mismatch: '{value.type._name}'."

                    assert value.type == dataType, f"Type mismatch for '{node['name']}'. (Expected '{dataType}', got '{value.type}'.)"
                    self.Builder.store(value, ptr, self.alignof(value).constant)

    @Timer
    def VisitAssign(self, node, ignore = False):
        assert self.scopeManager.Scope.local, "Assign statements must be defined in local scope."

        if "body" in node:
            for i in node["body"]:
                self.Compile([i])

        else:
            _ptr = ptr = self.VisitPointer(node["left"])

            while isinstance(_ptr, ir.GEPInstr):
                _ptr = _ptr.operands[0]

            if hasattr(_ptr.type, "_mutable") and hasattr(_ptr.type, "_name") and not ignore:
                assert _ptr.type._mutable, f"Cannot assign to an immutable variable: '{_ptr.type._name}'."

            if hasattr(ptr.type.pointee, "_reference"):
                ptr = self.Builder.load(ptr)

            assert ptr.type.is_pointer, "Left side of an assignment must be a pointer."

            if isinstance(ptr.type.pointee, ir.BaseStructType):
                _class = self.scopeManager.Get(ptr.type.pointee.name, types = [Class])

                if isinstance(node["right"], dict) and node["right"]["type"] in ["expression"] and node["left"] in [node["right"]["left"], node["right"]["right"]]:
                    value = self.TryPass(self.VisitValue(node["right"]["left" if node["left"] != node["right"]["left"] else "right"]))

                    if _class.Has(f"op{node['right']['operator']}=", arguments = [value.type]):
                        return self.VisitCall({"value": _class.Get(f"op{node['right']['operator']}=", arguments = [value], pointer = ptr), "params": [value]})

            value = self.TryPass(self.VisitValue(node["right"]))

            if isinstance(ptr.type.pointee, ir.BaseStructType):
                if _class.Has("op=", arguments = [value]):
                    self.VisitCall({"value": _class.Get("op=", arguments = [value], pointer = ptr), "params": [value]})
                    return ptr

                elif value.type == _class.type:
                    value = self.addressof(value)

                    for name, _ in _class.Elements.items():
                        self.VisitAssign({
                            "left": self.Builder.gep(ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]),
                            "right": self.Builder.load(self.Builder.gep(value, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), _class.Index(name))]))
                        })

                    return ptr

                else:
                    assert False, f"Type mismatch. (Expected '{_class.type}', got '{value.type}'.)"

            else:
                assert value.type == ptr.type.pointee, f"Type mismatch for '{ptr}'. (Expected '{ptr.type.pointee}', got '{value.type}'.)"
                self.Builder.store(value, ptr, self.alignof(value).constant)
                return ptr

    @Timer
    def VisitNew(self, node):
        assert self.scopeManager.Scope.local, "New statements must be defined in local scope."
        type = self.VisitType(node["value"])

        if node["count"]:
            count = self.VisitValue(node["count"])
            _ptr = self.Builder.call(self.malloc, [self.Builder.add(ir.Constant(ir.IntType(64), 8), self.Builder.mul(self.sizeof(type), count))])
            self.Builder.store(count, self.Builder.bitcast(_ptr, ir.IntType(64).as_pointer()))
            ptr = self.Builder.gep(self.Builder.bitcast(_ptr, ir.IntType(8).as_pointer()), [ir.Constant(ir.IntType(64), 8)])
            ptr = self.Builder.bitcast(ptr, type.as_pointer())

            if isinstance(type, ir.BaseStructType):
                value = self.Builder.alloca(ir.IntType(64))
                self.Builder.store(ir.Constant(ir.IntType(64), 0), value)

                compare = self.Builder.append_basic_block()
                loop = self.Builder.append_basic_block()
                end = self.Builder.append_basic_block()

                self.Builder.branch(compare)
                self.Builder.position_at_end(compare)
                index = self.Builder.load(value)
                self.Builder.cbranch(self.Builder.icmp_signed("<", index, count), loop, end)

                self.Builder.position_at_end(loop)
                self.VisitConstructor(self.scopeManager.Get(type.name, types = [Class]), self.Builder.gep(ptr, [index]), [])
                self.Builder.store(self.Builder.add(index, ir.Constant(ir.IntType(64), 1)), value, self.alignof(value).constant)
                self.Builder.branch(compare)
                self.Builder.position_at_end(end)

        else:
            params = [self.VisitValue(i) for i in node["params"]] if node["params"] else []
            ptr = self.Builder.bitcast(self.Builder.call(self.malloc, [self.sizeof(type)]), type.as_pointer())

            if isinstance(type, ir.BaseStructType):
                self.VisitConstructor(self.scopeManager.Get(type.name, types = [Class]), ptr, params)

            else:
                assert not params, "Cannot initialize non-class types with parameters."

        return ptr

    @Timer
    def VisitDelete(self, node):
        assert self.scopeManager.Scope.local, "Delete statements must be defined in local scope."
        ptr = self.VisitValue(node["value"])
        assert ptr.type.is_pointer, "Delete value must be a pointer."
        _ptr = self.Builder.bitcast(ptr, ir.IntType(8).as_pointer()) if ptr.type.pointee != ir.IntType(8) else ptr

        if node["array"]:
            _ptr = self.Builder.gep(_ptr, [ir.Constant(ir.IntType(32), -8)])
            count = self.Builder.load(self.Builder.bitcast(_ptr, ir.IntType(64).as_pointer()))

            if isinstance(ptr.type.pointee, ir.BaseStructType):
                value = self.Builder.alloca(ir.IntType(64))
                self.Builder.store(ir.Constant(ir.IntType(64), 0), value)

                compare = self.Builder.append_basic_block()
                loop = self.Builder.append_basic_block()
                end = self.Builder.append_basic_block()

                self.Builder.branch(compare)
                self.Builder.position_at_end(compare)
                index = self.Builder.load(value)
                self.Builder.cbranch(self.Builder.icmp_signed("<", index, count), loop, end)

                self.Builder.position_at_end(loop)
                self.VisitDestructor(self.scopeManager.Get(ptr.type.pointee.name, types = [Class]), self.Builder.gep(ptr, [index]))
                self.Builder.store(self.Builder.add(index, ir.Constant(ir.IntType(64), 1)), value, self.alignof(value).constant)
                self.Builder.branch(compare)
                self.Builder.position_at_end(end)

        else:
            if isinstance(ptr.type.pointee, ir.BaseStructType):
                self.VisitDestructor(self.scopeManager.Get(ptr.type.pointee.name, types = [Class]), ptr)

        self.Builder.call(self.free, [_ptr])

    @Timer
    def VisitCall(self, node):
        assert self.scopeManager.Scope.local, "Call statements must be defined in local scope."
        funcs = self.VisitPointer(node["value"])
        _params = [self.VisitValue(i) for i in node["params"]]
        func, name, best = None, None, -1

        if not isinstance(funcs, list):
            funcs = [funcs]

        for index, _func in enumerate(funcs):
            params = _params.copy()

            if isinstance(_func, CompileTimeFunction):
                func = _func
                assert len(funcs) == 1, "Cannot overload compile-time functions."
                break

            if isinstance(_func, dict) and "access" in _func:
                if _func["pointer"] not in node["params"]:
                    params = [self.VisitValue(_func["pointer"])] + params

                _func, _ptr = _func["type"], params[0]

                while isinstance(_ptr, ir.GEPInstr):
                    _ptr = _ptr.operands[0]

                if hasattr(_ptr.type, "_mutable") and False:
                    assert _ptr.type._mutable, f"Cannot call methods of an immutable class: '{_ptr.type._name}: {_ptr.type.pointee.name}'."

            if isinstance(_func, ir.AllocaInstr):
                _func = self.Builder.load(_func)

            name, _index, score = _func.name, 0, 0

            for j in _func.function_type.args:
                if hasattr(j, "_sret"):
                    continue

                if _index >= len(params):
                    score = -1
                    break

                target = j._byval if hasattr(j, "_byval") else j
                type = self.ProcessType(params[_index].type)
                _index += 1

                if hasattr(target, "_reference"):
                    target = target.pointee

                if type != target:
                    score = -1
                    break

                score += 1

            if len(params) < _index if _func.function_type.var_arg else len(params) != _index:
                continue

            if best < score:
                func, best = _func, score

        assert func is not None, f"Invalid arguments for: '{name}'. ({', '.join([str(i.type) for i in params]) if params else 'nothing'})"

        if isinstance(func, CompileTimeFunction):
            return func(*params)

        _return, args, index = None, [], -1

        if isinstance(func, ir.Function) and 0 < len(func.args):
            argument = func.args[0].type

            if hasattr(argument, "_sret"):
                current = self.Builder.block
                self.Builder.position_at_start(self.Builder.function.entry_basic_block)
                _return = self.Builder.alloca(argument._sret)
                self.Builder.position_at_end(current)

                if isinstance(argument._sret, ir.BaseStructType):
                    self.scopeManager.Scope.RegisterInstance(_return)

                _return._return = True
                args.append(_return)
                index += 1

        for value in params:
            index += 1

            if isinstance(func, ir.Function) and index < len(func.args):
                argument = func.args[index].type

                if hasattr(argument, "_byval"):
                    value = self.addressof(value)
                    current = self.Builder.block
                    self.Builder.position_at_start(self.Builder.function.entry_basic_block)
                    _class = self.scopeManager.Get(value.type.pointee.name, types = [Class])
                    ptr = self.Builder.alloca(value.type.pointee)
                    self.Builder.position_at_end(current)
                    self.VisitConstructor(_class, ptr, [self.Builder.load(value)])
                    value = ptr

                    if not isinstance(argument, ir.PointerType):
                        args.append(self.Builder.load(value, typ = argument))

                    else:
                        assert value.type.pointee == argument.pointee, \
                            f"Expected '{argument}', got '{value.type}'."

                        args.append(value)

                else:
                    value = self.TryPass(value)

                    if hasattr(argument, "_reference") and argument != value.type:
                        value = self.addressof(value)

                    args.append(value)

            else:
                args.append(self.TryPass(value))

        result = self.Builder.call(func, args)

        if _return is not None:
            return self.Builder.load(_return)

        if hasattr(result.type, "_sret"):
            assert isinstance(result.type, ir.IntType), f"Expected an integer, got '{result.type}'."

            current = self.Builder.block
            self.Builder.position_at_start(self.Builder.function.entry_basic_block)
            ptr = self.Builder.alloca(result.type._sret)
            self.Builder.position_at_end(current)
            self.Builder.store(result, self.Builder.bitcast(ptr, result.type.as_pointer()), self.alignof(result.type._sret).constant)

            if isinstance(result.type._sret, ir.BaseStructType):
                self.scopeManager.Scope.RegisterInstance(ptr)

            ptr._return, result = True, self.Builder.load(ptr)

        return result

    @Timer
    def VisitWhile(self, node):
        assert self.scopeManager.Scope.local, "While blocks must be defined in local scope."
        compareBlock = self.Builder.append_basic_block()
        loopBlock = self.Builder.append_basic_block()
        endBlock = self.Builder.append_basic_block()
        self.PushBlocks(loopBlock, endBlock)

        self.Builder.branch(compareBlock)
        self.Builder.position_at_start(compareBlock)
        condition = self.VisitValue(node["condition"])
        self.Builder.cbranch(condition, loopBlock, endBlock)

        self.Builder.position_at_start(loopBlock)
        self.scopeManager.PushScope(Scope(local = True))
        self.Compile(node["body"])
        self.scopeManager.PopScope()

        if not self.Builder.block.is_terminated:
            self.Builder.branch(compareBlock)

        self.Builder.position_at_start(endBlock)
        self.PopBlocks()

    @Timer
    def VisitReturn(self, node):
        assert self.scopeManager.Scope.local, "Return statements must be defined in local scope."

        if node["value"]:
            if hasattr(self.Builder.function.return_value.type, "_sret"):
                value = self.VisitPointer(node["value"])
                assert isinstance(value.type.pointee, ir.BaseStructType), "Expected a class."

                if isinstance(self.Builder.function.return_value.type, ir.IntType):
                    _value = self.Builder.load(value, typ = self.Builder.function.return_value.type)
                    self.InvokeDestructors(_except = value)
                    self.Builder.ret(_value)

                else:
                    assert isinstance(self.Builder.function.return_value.type, ir.VoidType), "Expected void return type."
                    _class = self.scopeManager.Get(value.type.pointee.name, types = [Class])
                    self.VisitConstructor(_class, self.Builder.function.args[0], [self.Builder.load(value)])
                    self.InvokeDestructors(_except = value)
                    self.Builder.ret_void()

            else:
                value = self.TryPass(self.VisitValue(node["value"]), _return = True)
                if hasattr(self.Builder.function.return_value.type, "_reference") and self.Builder.function.return_value.type != value.type: value = self.addressof(value)
                assert value.type == self.Builder.function.return_value.type, f"Return type mismatch for '{self.Builder.function.name}'. (Expected '{self.Builder.function.return_value.type}', got '{value.type}'.)"
                self.InvokeDestructors()
                self.Builder.ret(value)

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

            if isinstance(left.type, ir.BaseStructType) or isinstance(right.type, ir.BaseStructType):
                ptr, value = (left, right) if isinstance(left.type, ir.BaseStructType) else (right, left)
                _class = self.scopeManager.Get(ptr.type.name, types = [Class])
                ptr, value = self.addressof(ptr), self.TryPass(value)

                if _class.Has(f"op{node['operator']}", arguments = [value.type]):
                    return self.VisitCall({"value": _class.Get(f"op{node['operator']}", arguments = [value], pointer = ptr), "params": [value]})

            if left.type.is_pointer and right.type.is_pointer:
                if node["operator"] == "-":
                    return self.Builder.sub(self.Builder.ptrtoint(left, ir.IntType(64)), self.Builder.ptrtoint(right, ir.IntType(64)))

                elif node["operator"] in ["<", "<=", ">", ">=", "!=", "=="]:
                    return self.Builder.icmp_unsigned(node["operator"], left, right)

                else:
                    assert False, f"Invalid operator for pointers. ({left.type} {node["operator"]} {right.type})"

            elif (left.type.is_pointer and isinstance(right.type, ir.IntType)) or (right.type.is_pointer and isinstance(left.type, ir.IntType)):
                ptr, index = (left, right) if left.type.is_pointer else (right, left)
                assert index.type.width in [32, 64], f"Invalid index size: '{index.type.width}'."

                if node["operator"] in ["+", "-"]:
                    return self.Builder.gep(ptr, [index if node["operator"] != "-" else self.Builder.neg(index)])

                else:
                    assert False, f"Invalid operator for pointers. ({left.type} {node["operator"]} {right.type})"

            elif (isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType)) and (isinstance(right.type, ir.FloatType) or isinstance(right.type, ir.DoubleType)):
                assert left.type == right.type, f"Float size mismatch. ({left.type} {node["operator"]} {right.type})"

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
                    assert False, f"Invalid operator for floats. ({left.type} {node["operator"]} {right.type})"

            elif isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType):
                assert left.type.width == right.type.width, f"Integer size mismatch. ({left.type._to_string2()} {node["operator"]} {right.type._to_string2()})"
                assert (unsigned := hasattr(left.type, "_unsigned")) == hasattr(right.type, "_unsigned"), \
                    f"Integer sign mismatch. ({left.type._to_string2()} {node["operator"]} {right.type._to_string2()})"

                if node["operator"] == "+":
                    return self.Builder.add(left, right)

                elif node["operator"] == "*":
                    return self.Builder.mul(left, right)

                elif node["operator"] == "/":
                    if unsigned: return self.Builder.udiv(left, right)
                    else: return self.Builder.sdiv(left, right)

                elif node["operator"] == "%":
                    if unsigned: return self.Builder.urem(left, right)
                    else: return self.Builder.srem(left, right)

                elif node["operator"] == "-":
                    return self.Builder.sub(left, right)

                elif node["operator"] in ["<", "<=", ">", ">=", "!=", "=="]:
                    if unsigned: return self.Builder.icmp_unsigned(node["operator"], left, right)
                    else: return self.Builder.icmp_signed(node["operator"], left, right)

                elif node["operator"] in ["&", "&&"]:
                    return self.Builder.and_(left, right)

                elif node["operator"] in ["|", "||"]:
                    return self.Builder.or_(left, right)

                elif node["operator"] == "^":
                    return self.Builder.xor(left, right)

                elif node["operator"] == ">>":
                    if unsigned: return self.Builder.lshr(left, right)
                    else: return self.Builder.ashr(left, right)

                elif node["operator"] == "<<":
                    return self.Builder.shl(left, right)

                else:
                    assert False, f"Invalid operator for integers. ({left.type._to_string2()} {node["operator"]} {right.type._to_string2()})"

            else:
                assert False, f"Invalid expression. ({left.type} {node["operator"]} {right.type})"