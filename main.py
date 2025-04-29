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

    print(str(module))

    if False:
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
    
    workDir, fileName = os.getcwd(), argv[1].split(".")[0]
    libDirs, libs = [], ["kernel32", "msvcrt", "ucrt", "vcruntime", "libcmt", "legacy_stdio_definitions"]

    libs = ["kernel32", "msvcrt", "ucrt"]

    # winPath = R"C:\Program Files (x86)\Windows Kits\10\Lib"
    # libDirs.append(os.path.join(winPath, os.listdir(winPath)[0], "um", "x64"))
    # libDirs.append(os.path.join(winPath, os.listdir(winPath)[0], "ucrt", "x64"))

    # msvcPath = R"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC"
    # libDirs.append(os.path.join(msvcPath, os.listdir(msvcPath)[0], "lib", "x64"))
    # libDirs, libs = [f"/LIBPATH:{os.path.abspath(i).replace("\\", "/")}" for i in libDirs], [f"{i}.lib" for i in libs]
    libDirs, libs = [f"-L{os.path.abspath(i).replace("\\", "/")}" for i in libDirs], [f"-l{i}" for i in libs]

    # with open(f"{fileName}.llvm", "w") as file:
    #     file.write(str(module))

    os.chdir(tempfile.gettempdir())
    
    with open(f"{fileName}.llvm", "w") as file:
        file.write(str(module))

    result = subprocess.run(["opt", f"{fileName}.llvm", "-o", f"{fileName}.bc", "-O0"])
    if os.path.exists(f"{fileName}.llvm"): os.remove(f"{fileName}.llvm")
    if result.returncode != 0: return -1

    result = subprocess.run(["llc", "-filetype=obj", f"{fileName}.bc", "-o", f"{fileName}.o"])
    if os.path.exists(f"{fileName}.bc"): os.remove(f"{fileName}.bc")
    if result.returncode != 0: return -1

    subprocess.run(["g++", os.path.join(os.path.split(__file__)[0], "asm", "__chkstk.s").replace("\\", "/"), "-c", "-o", "__chkstk.o"])
    subprocess.run(["g++", "-g", "-O0", f"{fileName}.o", "__chkstk.o", "-o", os.path.join(workDir, f"{fileName}.exe").replace("\\", "/"), "-pthread", "-static", "-static-libgcc", "-static-libstdc++"] + libDirs + libs)
    
    # result = subprocess.run(["cl", f"{fileName}.obj", "/Zi", "/link", f"/OUT:{os.path.join(workDir, f"{fileName}.exe").replace('\\', '/')}"] + libDirs + libs)
    if os.path.exists(f"{fileName}.o"): os.remove(f"{fileName}.o")
    if result.returncode != 0: return -1

    os.chdir(workDir)
    subprocess.run([os.path.join(workDir, f"{fileName}.exe").replace("\\", "/")] + argv[2:])
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))