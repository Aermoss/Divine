import os, llvmlite, traceback

llvmlite.opaque_pointers_enabled = True

import sys, ctypes, collections.abc as abc
import llvmlite.binding as llvm

from lexer import Lexer
from parser import Parser
from compiler import Compiler

fileCache: dict[str, str] = {}

def CompileFile(file: str) -> llvm.ExecutionEngine:
    if file in fileCache: return fileCache[file]
    lexer, parser, compiler = Lexer(), Parser(), Compiler()
    parser.parse(lexer.Lex(open(file, "r").read()))
    compiler.includePaths.append("./include")
    module = compiler.Compile(parser.ast["body"])
    module.triple = llvm.get_default_triple()
    module = llvm.parse_assembly(str(module))
    module.verify()

    targetMachine = llvm.Target.from_default_triple().create_target_machine()
    engine = llvm.create_mcjit_compiler(module, targetMachine)
    engine.finalize_object()

    fileCache[file] = engine
    return engine

tests = {}

def RegisterTest(file: str, type: type) -> None:
    def __inner__(func: abc.Callable[..., None]) -> abc.Callable[..., None]:
        if file not in tests: tests[file] = []
        tests[file] += [(func, type)]
        return func

    return __inner__

@RegisterTest("Expression.div", ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double))
def SimpleExpression(func) -> None:
    result = func(x := 7)

    assert result == (expected := x + 2.32), \
        f"Expected {expected}, but got {result}."

@RegisterTest("Expression.div", ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double))
def ComplexExpression(func) -> None:
    result = func(x := 9)

    assert result == (expected := 8.0 + (x + 1) * 2.5), \
        f"Expected {expected}, but got {result}."

@RegisterTest("Expression.div", ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_bool, ctypes.c_bool))
def SimpleLogicalExpression(func) -> None:
    result = func(x := True, y := True)

    assert result == (expected := x and y), \
        f"Expected {expected}, but got {result}."
    
@RegisterTest("Expression.div", ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_bool, ctypes.c_bool, ctypes.c_bool))
def ComplexLogicalExpression(func) -> None:
    result = func(x := True, y := False, z := True)

    assert result == (expected := x and y or z), \
        f"Expected {expected}, but got {result}."

@RegisterTest("Expression.div", ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64, ctypes.c_int64))
def SimpleBitwiseExpression(func) -> None:
    result = func(x := 1, y := 2)

    assert result == (expected := x & y), \
        f"Expected {expected}, but got {result}."

@RegisterTest("Expression.div", ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64))
def ComplexBitwiseExpression(func) -> None:
    result = func(x := 1, y := 2, z := 3)

    assert result == (expected := x << y | z & 0xFF), \
        f"Expected {expected}, but got {result}."

@RegisterTest("FlowControl.div", ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int32))
def IfBlockTest(func) -> None:
    result = func(5)

    assert result == (expected := 10), \
        f"Expected {expected}, but got {result}."

    result = func(3)

    assert result == (expected := 7), \
        f"Expected {expected}, but got {result}."

    result = func(2)

    assert result == (expected := 5), \
        f"Expected {expected}, but got {result}."

@RegisterTest("FlowControl.div", ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int32))
def WhileBlockTest(func) -> None:
    result = func(5)

    assert result == (expected := 10), \
        f"Expected {expected}, but got {result}."

@RegisterTest("Convention.div", ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_float, ctypes.c_float))
def ByValSmallArgTest(func) -> None:
    result = func(x := 5.0, y := 10.0)

    assert result == (expected := x + y), \
        f"Expected {expected}, but got {result}."

@RegisterTest("Convention.div", ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_float, ctypes.c_float))
def ByValSmallRetTest(func) -> None:
    result = func(x := 2.0, y := 3.0)

    assert result == (expected := x + y), \
        f"Expected {expected}, but got {result}."

@RegisterTest("Convention.div", ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_float, ctypes.c_float, ctypes.c_float))
def ByValBigArgTest(func) -> None:
    result = func(x := 5.0, y := 10.0, z := 15.0)

    assert result == (expected := x + y + z), \
        f"Expected {expected}, but got {result}."

@RegisterTest("Convention.div", ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_float, ctypes.c_float, ctypes.c_float))
def ByValBigRetTest(func) -> None:
    result = func(x := 2.0, y := 3.0, z := 4.0)

    assert result == (expected := x + y + z), \
        f"Expected {expected}, but got {result}."

class String(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_char)),
        ("length", ctypes.c_size_t)
    ]

@RegisterTest("Template.div", ctypes.CFUNCTYPE(String, ctypes.c_char_p))
def StringTest(func) -> None:
    result = func((input := "Test").encode())
    data = ctypes.cast(result.data, ctypes.POINTER(ctypes.c_char * result.length))

    assert data.contents.value.decode() == f"{input}String", \
        f"Expected '{input}String', but got '{data.contents.value.decode()}'."

    ctypes.cdll.msvcrt.free(result.data)

@RegisterTest("Template.div", ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double))
def VectorTest(func) -> None:
    result = func(input := 5.0)

    assert result == (expected := input + 10.0), \
        f"Expected '{expected}', but got '{result}'."

def RunAllTests() -> None:
    print("\33[32m", f"Initializing tests... (triple: {llvm.get_default_triple()}).", "\33[0m", sep = "", flush = True)
    passed, failed = 0, 0

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    for file, _tests in tests.items():
        file = os.path.join("tests", file)
        engine = CompileFile(file)

        for func, type in _tests:
            try:
                func(type(engine.get_function_address(func.__name__)))
                print("\33[32m", f"Test '{func.__name__}' passed.", "\33[0m", sep = "", flush = True)
                passed += 1

            except AssertionError as exc:
                print("\33[31m", f"Test '{func.__name__}' failed: {str(exc).capitalize()}", "\33[0m", sep = "", flush = True)
                failed += 1

    print("\33[31m" if failed else "\33[32m", f"{'Failed' if failed else 'Passed'}! {passed} test(s) passed, {failed} test(s) failed.", "\33[0m", sep = "", flush = True)
    return -1 if failed else 0

def main(argv: list[str]) -> int:
    return RunAllTests()

if __name__ == "__main__":
    sys.exit(main(sys.argv))