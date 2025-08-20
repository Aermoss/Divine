import os, sys, time, tempfile, subprocess
import json, sly, llvmlite.binding as llvm

# sly.yacc.SlyLogger.warning = lambda self, msg, *args, **kwargs: ...

from lexer import Lexer
from parser import Parser
from compiler import Compiler

from ctypes import *

def main(argv):
    lexer, parser, compiler = Lexer(), Parser(), Compiler()
    parser.parse(lexer.Lex(open(argv[1], "r").read()))

    with open("ast.json", "w") as file:
        file.write(json.dumps(parser.ast, indent = 4))

    compiler.includePaths.append("./include")
    module = compiler.Compile(parser.ast["body"])
    module.triple = llvm.get_default_triple()
    del compiler

    if False:
        print(str(module))

        llvm.initialize()
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()

        module = llvm.parse_assembly(str(module))
        module.verify()

        targetMachine = llvm.Target.from_default_triple().create_target_machine()
        engine = llvm.create_mcjit_compiler(module, targetMachine)
        engine.finalize_object()

        start = time.time()
        main = CFUNCTYPE(c_int)(engine.get_function_address("main"))
        result = main(len(argv), (c_char_p * len(argv))(*[i.encode("utf-8") for i in argv]))

        print(f"Program finished with code {result}.")
        print(f"Executed in {time.time() - start} seconds.")
        return
    
    libDirs, libs, debug = [], [], True
    workDir, fileName = os.getcwd(), argv[1].split(".")[0]

    with open(f"{fileName}.llvm", "w") as file:
        file.write(str(module))

    os.chdir(tempfile.gettempdir())

    with open(f"{fileName}.llvm", "w") as file:
        file.write(str(module))

    result = subprocess.run(["opt", f"{fileName}.llvm", "-o", f"{fileName}.bc", "-O0"])
    if os.path.exists(f"{fileName}.llvm"): os.remove(f"{fileName}.llvm")
    if result.returncode != 0: return -1

    result = subprocess.run(["llc", "-filetype=obj", f"{fileName}.bc", "-o", f"{fileName}.obj"])
    if os.path.exists(f"{fileName}.bc"): os.remove(f"{fileName}.bc")
    if result.returncode != 0: return -1

    # result = subprocess.run(["clang", "-c", os.path.join(os.path.split(__file__)[0], "asm", "__chkstk.asm"), "-o", "__chkstk.obj"])
    # if os.path.exists(f"__chkstk.obj"): os.remove(f"__chkstk.obj")
    # if result.returncode != 0: return -1

    libDirs, libs = [f"-L{os.path.abspath(dir).replace("\\", "/")}" for dir in libDirs], [f"-l{lib}" for lib in libs]
    result = subprocess.run(["clang"] + (["-g", "-O0"] if debug else []) + [f"{fileName}.obj", "-o", os.path.join(workDir, f"{fileName}.exe")] + libDirs + libs)
    if os.path.exists(f"{fileName}.obj"): os.remove(f"{fileName}.obj")
    if result.returncode != 0: return -1

    os.chdir(workDir)
    subprocess.run([os.path.join(workDir, f"{fileName}.exe").replace("\\", "/")] + argv[2:])
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))