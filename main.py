import os, sys, tempfile, subprocess
import llvmlite.binding as llvm

from lexer import Lexer
from parser import Parser
from compiler import Compiler

def main(argv):
    lexer, parser, compiler = Lexer(), Parser(), Compiler()
    parser.parse(lexer.Lex(open(argv[1], "r").read()))
    compiler.includePaths.append("./include")
    module = compiler.Compile(parser.ast["body"])
    module.name = os.path.splitext(os.path.basename(argv[1]))[0]
    module.triple = llvm.get_default_triple()

    libDirs, libs, debug, msvc = ["./lib"], ["raylibdll", "legacy_stdio_definitions", "msvcrt", "ucrt", "vcruntime"], True, True
    if not msvc: libDirs, libs = [f"-L{os.path.abspath(dir).replace("\\", "/")}" for dir in libDirs], [f"-l{lib}" for lib in libs]
    else: libDirs, libs = ["/link"] + [f"/LIBPATH:{os.path.abspath(dir).replace("/", "\\")}" for dir in libDirs], [f"{lib}.lib" for lib in libs]
    workDir, fileName = os.getcwd(), os.path.splitext(argv[1])[0]

    with open(f"{fileName}.llvm", "w") as file:
        file.write(str(module))

    os.chdir(tempfile.gettempdir())

    with open(f"{fileName}.llvm", "w") as file:
        file.write(str(module))

    result = subprocess.run(["opt", f"{fileName}.llvm", "-o", f"{fileName}.bc", "-O0"] + (["-O0"] if debug else []))
    if os.path.exists(f"{fileName}.llvm"): os.remove(f"{fileName}.llvm")
    if result.returncode != 0: return -1

    result = subprocess.run(["llc", "-filetype=obj", f"{fileName}.bc", "-o", f"{fileName}.obj"] + (["-O0"] if debug else []))
    if os.path.exists(f"{fileName}.bc"): os.remove(f"{fileName}.bc")
    if result.returncode != 0: return -1

    if not msvc: result = subprocess.run(["clang"] + (["-g", "-O0"] if debug else []) + [f"{fileName}.obj", "-o", os.path.join(workDir, f"{fileName}.exe")] + libDirs + libs)
    else: result = subprocess.run(["clang-cl"] + (["/Zi", "/Od"] if debug else []) + [f"{fileName}.obj", f"/Fe:{os.path.join(workDir, f'{fileName}.exe')}"] + libDirs + libs)
    if os.path.exists(f"{fileName}.obj"): os.remove(f"{fileName}.obj")
    if result.returncode != 0: return -1

    os.chdir(workDir)
    subprocess.run([os.path.join(workDir, f"{fileName}.exe").replace("\\", "/")] + argv[2:])
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))